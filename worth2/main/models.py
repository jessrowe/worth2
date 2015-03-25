import re

from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.shortcuts import get_object_or_404
from ordered_model.models import OrderedModel
from pagetree.reports import PagetreeReport, StandaloneReportColumn
from pagetree.generic.models import BasePageBlock

from worth2.main.auth import user_is_participant
from worth2.main.generic.models import BaseUserProfile


class InactiveUserProfile(BaseUserProfile):
    """WORTH's UserProfile, which is only being used on participants."""

    # Participants have a created_by attr pointing to the facilitator
    # that created them.
    created_by = models.ForeignKey(User, null=True, blank=True,
                                   related_name='created_by')
    is_archived = models.BooleanField(default=False)

    def is_participant(self):
        return (not self.user.is_active)


class Avatar(OrderedModel):
    """An image that the participant can choose for their profile."""

    image = models.ImageField()

    is_default = models.BooleanField(
        default=False,
        help_text='If this is the initial avatar for all participants, ' +
        'set this option to True. There can only be one default avatar ' +
        'in the system.')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return unicode(self.image.url)

    def clean(self):
        if self.is_default:
            qs = Avatar.objects.filter(is_default=True)
            if qs.count() > 0 and self.pk != qs.first().pk:
                raise ValidationError(
                    '%s is already set as the default.' % qs.first())


class AvatarBlock(BasePageBlock):
    """A PageBlock for displaying the current participant's avatar."""

    display_name = 'Avatar Block'
    template_file = 'main/avatar_block.html'

    @classmethod
    def add_form(cls):
        return AvatarBlockForm()

    def edit_form(self):
        return AvatarBlockForm(instance=self)

    @classmethod
    def create(cls, request):
        form = AvatarBlockForm(request.POST)
        return form.save()

    def edit(self, vals, files):
        form = AvatarBlockForm(data=vals, files=files, instance=self)
        if form.is_valid():
            form.save()


class AvatarBlockForm(forms.ModelForm):
    class Meta:
        model = AvatarBlock


class AvatarSelectorBlock(BasePageBlock):
    """A PageBlock for displaying the Avatar Selector."""

    display_name = 'Avatar Selector Block'
    template_file = 'main/avatar_selector_block.html'

    def needs_submit(self):
        return True

    def unlocked(self, user):
        # Avatar selection is optional. Participants start
        # out with a default avatar.
        return True

    def submit(self, user, request_data):
        if user_is_participant(user):
            avatar_id = request_data.get('avatar-id')
            avatar = get_object_or_404(Avatar, pk=avatar_id)
            user.profile.participant.avatar = avatar
            user.profile.participant.save()

    def clear_user_submissions(self, user):
        if user_is_participant(user):
            user.profile.participant.avatar = None
            user.profile.participant.save()

    def avatars(self):
        """Returns a queryset of all the available avatars in WORTH."""

        return Avatar.objects.all()

    @staticmethod
    def add_form():
        return AvatarSelectorBlockForm()

    def edit_form(self):
        return AvatarSelectorBlockForm(instance=self)

    @staticmethod
    def create(request):
        form = AvatarSelectorBlockForm(request.POST)
        return form.save()

    @classmethod
    def create_from_dict(cls, d):
        return cls.objects.create()

    def edit(self, vals, files):
        form = AvatarSelectorBlockForm(data=vals, files=files, instance=self)
        if form.is_valid():
            form.save()


class AvatarSelectorBlockForm(forms.ModelForm):
    class Meta:
        model = AvatarSelectorBlock


class Location(models.Model):
    """A physical location where an intervention takes place.

    Time and place are used to create the participants' cohort
    (implemented as a group).
    """

    name = models.TextField()

    def __unicode__(self):
        return unicode(self.name)


# A user in WORTH 2 can either be:
# - A participant
# - A facilitator
# - A research assistant
# - A researcher
# - A superuser
#
# Some of these types of users have special data associated with them.

# ID spec is here:
# http://wiki.ccnmtl.columbia.edu/index.php/WORTH_2_User_Stories#Participant_ID_number_scheme
study_id_validator = RegexValidator(
    regex=r'^\d{12}$',
    message='That study ID isn\'t valid. (It needs to be 12 digits)')

# For now, accept any 3-digit number as the cohort ID.
cohort_id_validator = RegexValidator(
    regex=r'^\d{3}$',
    message='That cohort ID isn\'t valid. (It needs to be 3 digits)')


class ParticipantManager(models.Manager):
    def cohort_ids(self):
        """
        Get a list of all the unique cohort IDs that have been entered
        on the participants.
        """

        ids = self.all().values_list(
            'cohort_id', flat=True
        ).exclude(
            cohort_id__isnull=True
        ).exclude(
            cohort_id__exact='').distinct()

        return sorted(ids)


class Participant(InactiveUserProfile):
    """ A Participant is a worth-specific inactive user profile.
    """
    # first_location is set the first time that a facilitator signs in a
    # participant. This is used to infer the participant's cohort group.
    first_location = models.ForeignKey(Location, blank=True, null=True,
                                       related_name='first_location')

    # location is set each time a facilitator signs in a participant.
    location = models.ForeignKey(Location, blank=True, null=True)

    # A study ID is pre-generated for each participant, and then entered
    # into our system.
    study_id = models.CharField(max_length=255,
                                unique=True,
                                db_index=True,
                                validators=[study_id_validator])

    # The cohort ID is assigned when the participant begins the second
    # session. It represents the group of all the participants present
    # for that session. It doesn't change for subsequent sessions, even
    # though there may be different participants present.
    cohort_id = models.CharField(max_length=255,
                                 blank=True,
                                 null=True,
                                 db_index=True,
                                 validators=[cohort_id_validator])

    # Participants can choose an avatar after their user is created.
    avatar = models.ForeignKey(Avatar, blank=True, null=True)

    objects = ParticipantManager()

    def __unicode__(self):
        return unicode(self.study_id)

    def last_session_accessed(self, url=None):
        """Get which session this participant is in. Returns an int."""

        if url is None:
            url = self.last_location_url()

        m = re.match(r'^/pages/session-(\d+)/.*', url)
        if m:
            return int(m.groups()[0])

        return None


class Session(models.Model):
    """A Session represents a participant going through a WORTH session.

    A Session is created each time a facilitator logs in a participant.
    """

    facilitator = models.ForeignKey(User)
    participant = models.ForeignKey(Participant)
    location = models.ForeignKey(Location)
    session_type = models.CharField(
        max_length=255,
        choices=(('regular', 'Regular'), ('makeup', 'Make-Up')),
        default='regular',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return unicode('Session for ' + self.participant.user.username)


class VideoBlock(BasePageBlock):
    display_name = 'YouTube Video Block'
    template_file = 'main/video_block.html'
    js_template_file = 'main/video_block_js.html'
    css_template_file = 'main/video_block_css.html'

    video_id = models.CharField(
        max_length=255, null=True,
        help_text='The YouTube video id, e.g. "M7lc1UVf-VE"'
    )

    @staticmethod
    def add_form():
        return VideoBlockForm()

    def edit_form(self):
        return VideoBlockForm(instance=self)

    @staticmethod
    def create(request):
        form = VideoBlockForm(request.POST)
        return form.save()

    def edit(self, vals, files):
        form = VideoBlockForm(data=vals, files=files, instance=self)
        if form.is_valid():
            form.save()


class VideoBlockForm(forms.ModelForm):
    class Meta:
        model = VideoBlock


class WatchedVideo(models.Model):
    """This model records which users have viewed which videos."""

    class Meta:
        unique_together = ('user', 'video_id')

    user = models.ForeignKey(User, related_name='watched_videos')
    video_id = models.CharField(max_length=255, db_index=True,
                                help_text='The youtube video ID',
                                null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class WorthRawDataReport(PagetreeReport):

    def users(self):
        users = User.objects.filter(is_active=False)
        return users.order_by('id')

    def standalone_columns(self):
        return [StandaloneReportColumn(
                'study_id', 'profile', 'string', 'Randomized Study Id',
                lambda x: x.profile.participant.study_id),
                StandaloneReportColumn(
                'cohort_id', 'profile', 'string', 'Assigned Cohort Id',
                lambda x: x.profile.participant.cohort_id)]
