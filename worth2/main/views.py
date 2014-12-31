from django import http
from django.contrib.auth import authenticate, login
from django.core.urlresolvers import reverse
from django.views.generic.base import TemplateView
from django.views.generic.list import ListView
from django.shortcuts import get_object_or_404, redirect

from pagetree.generic.views import PageView

from worth2.main.auth import generate_password, user_is_participant
from worth2.main.mixins import ActiveUserRequiredMixin
from worth2.main.models import Avatar, Location, Participant, Session


class AvatarSelector(TemplateView):
    template_name = 'main/avatar_selector.html'

    def get_context_data(self, **kwargs):
        ctx = super(AvatarSelector, self).get_context_data(**kwargs)
        ctx['avatars'] = Avatar.objects.all()
        return ctx

    def post(self, request, *args, **kwargs):
        avatar_id = request.POST.get('avatar_id')
        avatar = get_object_or_404(Avatar, pk=avatar_id)
        request.user.profile.participant.avatar = avatar
        request.user.profile.participant.save()
        return redirect(reverse('avatar-selector'))


class IndexView(ActiveUserRequiredMixin, TemplateView):
    template_name = 'main/index.html'

    def dispatch(self, *args, **kwargs):
        user = self.request.user
        if user_is_participant(user):
            return http.HttpResponseRedirect(user.profile.last_location_url())

        return super(IndexView, self).dispatch(*args, **kwargs)


class ManageParticipants(ActiveUserRequiredMixin, ListView):
    model = Participant

    def get_context_data(self, **kwargs):
        ctx = super(ManageParticipants, self).get_context_data(**kwargs)
        ctx['active_participants'] = [p for p in ctx['object_list']
                                      if not p.is_archived]
        ctx['archived_participants'] = [p for p in ctx['object_list']
                                        if p.is_archived]
        return ctx


class SignInParticipant(ActiveUserRequiredMixin, TemplateView):
    template_name = 'main/facilitator_sign_in_participant.html'

    def get_context_data(self, **kwargs):
        context = super(SignInParticipant, self).get_context_data(**kwargs)
        context['active_participants'] = Participant.objects.filter(
            is_archived=False)
        context['locations'] = Location.objects.all()
        return context

    def post(self, request, *args, **kwargs):
        participant = get_object_or_404(
            Participant, pk=request.POST['participant_id'])
        password = generate_password(participant.user.username)
        user = authenticate(
            username=participant.user.username, password=password)

        if user is not None:
            location = get_object_or_404(
                Location, pk=request.POST['participant_location'])

            # Create a Session and log in the participant
            Session.objects.get_or_create(
                participant=participant,
                defaults={'facilitator': request.user, 'location': location}
            )

            login(request, user)

            dest = request.POST['participant_destination']

            if dest == 'last_completed_activity':
                # TODO: redirect to the last completed activity
                pass
            elif dest == 'next_new_session':
                # TODO: redirect to the next new session
                pass
            elif dest == 'already_completed_session':
                # TODO redirect to the session that the user chose
                # session = request.POST['already_completed_session']
                pass

            # Go to the first session in pagetree
            return redirect('/pages/session-1/')

        raise http.Http404


class SessionPageView(PageView):
    """WORTH version of pagetree's PageView"""
    gated = True

    def gate_check(self, user):
        r = super(SessionPageView, self).gate_check(user)
        if r is not None:
            return r

        # Has the participant picked an avatar yet?
        if hasattr(user, 'profile') and user.profile.is_participant():
            if not user.profile.participant.avatar:
                return redirect(reverse('avatar-selector'))
