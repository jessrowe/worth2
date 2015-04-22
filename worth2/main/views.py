import unicodecsv

from django import http
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.http.response import StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template import TemplateDoesNotExist
from django.utils.decorators import method_decorator
from django.views.generic.base import TemplateView
from django.views.generic.edit import FormView
from django.views.generic.list import ListView
from pagetree.generic.views import PageView
from pagetree.models import PageBlock, Hierarchy, Section
from quizblock.models import Quiz

from worth2.goals.mixins import GoalCheckInViewMixin, GoalSettingViewMixin
from worth2.goals.models import GoalSettingResponse
from worth2.main.auth import generate_password, user_is_participant
from worth2.main.forms import SignInParticipantForm
from worth2.main.models import Encounter, Participant, Location
from worth2.main.reports import ParticipantReport
from worth2.main.utils import (
    get_first_block_in_module, get_first_block_of_type
)
from worth2.protectivebehaviors.utils import remove_empty_submission
from worth2.selftalk.mixins import (
    SelfTalkStatementViewMixin, SelfTalkRefutationViewMixin
)
from worth2.ssnm.models import Supporter


def get_quiz_blocks(css_class):
    quiz_type = ContentType.objects.get_for_model(Quiz)
    blocks = PageBlock.objects.filter(css_extra__contains=css_class,
                                      content_type=quiz_type)
    return blocks


def has_responses(section):
    quizzes = [p.block() for p in section.pageblock_set.all()
               if hasattr(p.block(), 'needs_submit')
               and p.block().needs_submit()]
    return quizzes != []


class IndexView(TemplateView):
    template_name = 'main/index.html'

    def dispatch(self, *args, **kwargs):
        user = self.request.user
        if user_is_participant(user):
            last_location = user.profile.last_location_url()
            if last_location == '/':
                # To prevent a redirect loop, if the participant's last
                # location is this index page, then default to showing them
                # the pagetree root.
                return http.HttpResponseRedirect('/pages/')
            else:
                return http.HttpResponseRedirect(last_location)

        return super(IndexView, self).dispatch(*args, **kwargs)


class ManageParticipants(ListView):
    model = Participant

    def get_queryset(self):
        return Participant.objects.order_by('study_id')

    def get_context_data(self, **kwargs):
        ctx = super(ManageParticipants, self).get_context_data(**kwargs)
        ctx['active_participants'] = [p for p in ctx['object_list']
                                      if not p.is_archived]
        ctx['archived_participants'] = [p for p in ctx['object_list']
                                        if p.is_archived]
        ctx['cohorts'] = Participant.objects.cohort_ids()
        return ctx


class ParticipantJournalView(TemplateView):
    model = Participant

    @staticmethod
    def _get_goal_responses(goalsettingblock, user):
        return GoalSettingResponse.objects.filter(
            goal_setting_block=goalsettingblock.block(),
            user=user)

    def get_context_data(self, **kwargs):
        context = super(ParticipantJournalView, self).get_context_data(
            **kwargs)
        # Participant's pk is in the URL
        context['participant'] = get_object_or_404(Participant,
                                                   pk=kwargs.get('pk'))
        try:
            session_num = int(kwargs.get('session_num'))
        except:
            raise http.Http404

        if session_num == 1:
            # Find the first 'services' type goal setter in Session 1
            goalsettingblock = get_first_block_in_module(
                'goal setting block', 1,
                lambda (b): b.block().goal_type == 'services')
            context['goal_responses'] = self._get_goal_responses(
                goalsettingblock, context['participant'].user)
        elif session_num == 2:
            pass
        elif session_num == 3:
            context['supporters'] = Supporter.objects.filter(
                user=context['participant'].user)
        elif session_num == 4:
            pass
        elif session_num == 5:
            pass
        else:
            raise http.Http404

        return context

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)

        try:
            session_num = int(kwargs.get('session_num'))
        except:
            raise http.Http404

        try:
            return render(request,
                          'main/session_%d_journal.html' % session_num,
                          context)
        except TemplateDoesNotExist:
            raise http.Http404


class SignInParticipant(FormView):
    template_name = 'main/facilitator_sign_in_participant.html'
    form_class = SignInParticipantForm

    def get_context_data(self, **kwargs):
        ctx = super(SignInParticipant, self).get_context_data(**kwargs)
        ctx.update({'cohorts': Participant.objects.cohort_ids()})
        return ctx

    def form_valid(self, form):
        participant = form.cleaned_data.get('participant_id')
        facilitator = self.request.user
        password = generate_password(participant.user.username)

        user = authenticate(
            username=participant.user.username, password=password)

        if user is not None:
            login(self.request, user)

            dest = form.cleaned_data.get('participant_destination')

            # Go to the first session in pagetree by default.
            section = get_object_or_404(Section, slug='session-1')

            if dest == 'last_completed_activity':
                section = participant.last_location()
            elif dest == 'next_new_session':
                section = participant.next_module_section()
            elif dest == 'already_completed_session':
                session_num = form.cleaned_data.get(
                    'already_completed_session')
                slug = 'session-%s' % session_num
                section = get_object_or_404(Section, slug=slug)

            Encounter.objects.create(
                participant=participant,
                facilitator=facilitator,
                location=form.cleaned_data.get('participant_location'),
                session_type=form.cleaned_data.get('session_type'),
                section=section)
            return redirect(section.get_absolute_url())

        return http.HttpResponse('Unauthorized', status=401)


class ParticipantSessionPageView(
        GoalCheckInViewMixin, GoalSettingViewMixin,
        SelfTalkStatementViewMixin, SelfTalkRefutationViewMixin,
        PageView):
    """WORTH version of pagetree's PageView."""

    gated = False

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        path = kwargs['path']
        self.section = self.get_section(path)
        self.goalsettingblock = get_first_block_of_type(
            self.section, 'goal setting block')
        self.goalcheckinblock = get_first_block_of_type(
            self.section, 'goal check in page block')
        self.selftalkstatementblock = get_first_block_of_type(
            self.section, 'statement block')
        self.selftalkrefutationblock = get_first_block_of_type(
            self.section, 'refutation block')

        if self.goalsettingblock:
            self.create_goal_setting_formset(
                request, self.goalsettingblock)
        elif self.goalcheckinblock:
            self.create_goal_check_in_formset(
                request, self.goalcheckinblock)
        elif self.selftalkstatementblock:
            self.create_selftalk_statement_form(
                request, self.selftalkstatementblock)
        elif self.selftalkrefutationblock:
            self.create_selftalk_refutation_form(
                request, self.selftalkrefutationblock)

        return super(ParticipantSessionPageView, self).dispatch(
            request, *args, **kwargs)

    def get_extra_context(self):
        ctx = super(ParticipantSessionPageView, self).get_extra_context()

        if self.goalsettingblock:
            ctx.update({'setting_formset': self.setting_formset})
        elif self.goalcheckinblock:
            ctx.update({
                'checkin_formset': self.checkin_formset,
                'goal_checkin_context': self.goal_checkin_context,
            })
        elif self.selftalkstatementblock:
            ctx.update({
                'statement_form': self.statement_form,
            })
        elif self.selftalkrefutationblock:
            ctx.update({
                'refutation_form': self.refutation_form,
            })

        avatarselectorblock = get_first_block_of_type(
            self.section, 'avatar selector block')
        ctx.update({'avatarselectorblock': avatarselectorblock})

        return ctx

    def get_context_data(self, **kwargs):
        allow_redo = False
        needs_submit = self.section.needs_submit()
        if needs_submit:
            allow_redo = self.section.allow_redo()
        context = dict(
            section=self.section,
            module=self.module,
            needs_submit=needs_submit,
            allow_redo=allow_redo,
            is_submitted=self.section.submitted(self.request.user),
            modules=self.root.get_children(),
            root=self.section.hierarchy.get_root(),
        )
        context.update(self.get_extra_context())
        return context

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        self.upv.visit()
        instructor_link = has_responses(self.section)

        # This flag is always False on non-protective behaviors quizzes.
        is_submission_empty = remove_empty_submission(request.user,
                                                      self.section)
        context.update({
            'is_submission_empty': is_submission_empty,
            'instructor_link': instructor_link,
        })
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        if request.POST.get('action') != 'reset':
            if self.goalsettingblock:
                return self.goal_setting_post(request, self.goalsettingblock)
            elif self.goalcheckinblock:
                return self.goal_check_in_post(request, self.goalcheckinblock)
            elif self.selftalkstatementblock:
                return self.selftalk_statement_post(
                    request, self.selftalkstatementblock)
            elif self.selftalkrefutationblock:
                return self.selftalk_refutation_post(
                    request, self.selftalkrefutationblock)

        return super(ParticipantSessionPageView, self).post(
            request, *args, **kwargs)


class Echo(object):
    """An object that implements just the write method of the file-like
    interface.
    """
    def write(self, value):
        """Write the value by returning it, instead of storing in a buffer."""
        return value


class ParticipantReportView(TemplateView):
    template_name = 'main/participant_report.html'

    def facilitators(self):
        rows = [['Facilitator ID', 'Facilitator Name']]
        for user in User.objects.filter(is_active=True, is_superuser=False):
            rows.append([user.id, user.username, user.get_full_name()])
        return rows

    def locations(self):
        rows = [['Location ID', 'Location Name']]
        for location in Location.objects.all():
            rows.append([location.id, location.name])
        return rows

    def post(self, request):
        hierarchies = Hierarchy.objects.filter(name="main")

        report_type = request.POST.get('report-type', 'keys')
        report = ParticipantReport(hierarchies[0])

        if report_type == 'facilitators':
            rows = self.facilitators()
        elif report_type == 'locations':
            rows = self.locations()
        elif report_type == 'values':
            rows = report.values(hierarchies)
        else:
            rows = report.metadata(hierarchies)

        pseudo_buffer = Echo()
        writer = unicodecsv.writer(pseudo_buffer)

        fnm = "worth2_%s.csv" % report_type
        response = StreamingHttpResponse(
            (writer.writerow(row) for row in rows), content_type="text/csv")
        response['Content-Disposition'] = 'attachment; filename="' + fnm + '"'
        return response
