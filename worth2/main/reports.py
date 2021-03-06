from datetime import timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from pagetree.models import UserPageVisit
from pagetree.reports import PagetreeReport, StandaloneReportColumn

from worth2.main.models import Encounter
from worth2.ssnm.models import SsnmReport


class ParticipantReport(PagetreeReport):

    five_minutes = timedelta(minutes=5)
    fifteen_minutes = timedelta(minutes=15)

    @classmethod
    def get_descendants(cls, section):
        key = 'hierarchy_%s_section_%s' % (section.hierarchy.id, section.id)
        descendants = cache.get(key)
        if descendants is None:
            descendants = section.get_descendants()
            cache.set(key, descendants)
        return descendants

    @classmethod
    def get_descendant_ids(cls, section):
        key = 'hierarchy_%s_sectionids_%s' % (section.hierarchy.id, section.id)
        ids = cache.get(key)
        if ids is None:
            descendants = cls.get_descendants(section)
            ids = [s.id for s in descendants]
            cache.set(key, ids)
        return ids

    @classmethod
    def format_timedelta(cls, delta):
        hours, remainder = divmod(delta.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        return '%02d:%02d:%02d' % (hours, minutes, seconds)

    def __init__(self, hierarchy):
        self.hierarchy = hierarchy
        super(ParticipantReport, self).__init__()

    def users(self):
        users = User.objects.filter(is_active=False,
                                    userpagevisit__isnull=False).distinct()
        return users.order_by('id')

    def encounter_id(self, participant, module_idx, module, encounter_idx):
        section_ids = self.get_descendant_ids(module)
        section_ids.append(module.id)
        encounters = Encounter.objects.filter(participant=participant,
                                              section__id__in=section_ids)
        if encounters.count() <= encounter_idx:
            return None
        else:
            encounter = encounters.order_by('created_at')[encounter_idx]
            return "%s-%d-%05d-%s-%d-%02d" % (
                participant.cohort_id,  # Cohort ID #: 3 digits
                module_idx + 1,  # Module #, 1 digit
                encounter.facilitator.id,  # Facilitator (5 digits)
                encounter.created_at.strftime("%y%m%d%I%M"),  # YYMMDDHHMM
                encounter_idx,
                encounter.location.id  # Location (2 digits)
            )

    def percent_complete(self, user, section):
        section_ids = self.get_descendant_ids(section)
        if not section.is_root():
            section_ids.insert(0, section.id)

        count = len(section_ids)
        if count == 0:
            return 0
        else:
            visits = UserPageVisit.objects.filter(user=user,
                                                  status='complete',
                                                  section__in=section_ids)
            return len(visits) / float(count) * 100

    def modules_completed(self, user):
        complete = 0

        for module in self.hierarchy.get_root().get_children():
            if self.percent_complete(user, module) == 100:
                complete += 1
            else:
                break
        return complete

    def time_spent(self, user, section):
        section_ids = self.get_descendant_ids(section)
        section_ids.insert(0, section.id)

        visits = UserPageVisit.objects.filter(user=user,
                                              status='complete',
                                              section__in=section_ids)

        time_spent = timedelta(0)
        prev = None
        for page in visits.order_by('first_visit'):
            if prev:
                interval = (page.first_visit - prev)
                if interval > self.fifteen_minutes:
                    # record 5 minutes for any interval longer than 15 minutes
                    time_spent += min(interval, self.five_minutes)
                else:
                    time_spent += interval
            prev = page.first_visit

        return self.format_timedelta(time_spent)

    def per_module_columns(self, module_idx, module):
        return [
            StandaloneReportColumn(
                '%s_time_spent' % module_idx, 'profile', 'string',
                '%s Time Spent' % module.label,
                lambda x: self.time_spent(x, module)),
            StandaloneReportColumn(
                '%s_encounter_id' % module_idx, 'profile', 'string',
                '%s Encounter Id' % module.label,
                lambda x: self.encounter_id(x.profile.participant, module_idx,
                                            module, 0)),
            StandaloneReportColumn(
                '%s_first_makeup_id' % module_idx, 'profile', 'string',
                '%s First Makeup Id' % module.label,
                lambda x: self.encounter_id(x.profile.participant, module_idx,
                                            module, 1)),
            StandaloneReportColumn(
                '%s_second_makeup_id' % module_idx, 'profile', 'string',
                '%s Second Makeup Id' % module.label,
                lambda x: self.encounter_id(x.profile.participant, module_idx,
                                            module, 2))
        ]

    def standalone_columns(self):
        base_columns = [
            StandaloneReportColumn(
                'study_id', 'profile', 'string', 'Randomized Study Id',
                lambda x: x.profile.participant.study_id),
            StandaloneReportColumn(
                'cohort_id', 'profile', 'string', 'Assigned Cohort Id',
                lambda x: x.profile.participant.cohort_id),
            StandaloneReportColumn(
                'modules_completed', 'profile', 'count', 'modules completed',
                lambda x: self.modules_completed(x)),
        ]

        for idx, module in enumerate(self.hierarchy.get_root().get_children()):
            base_columns += self.per_module_columns(idx + 1, module)

        return base_columns

    def metadata_columns(self, hierarchies):
        columns = super(ParticipantReport, self).metadata_columns(hierarchies)

        # not associated with hierarchy, but vary with metadata/values
        ssnm = SsnmReport()
        columns += ssnm.report_metadata()
        return columns

    def value_columns(self, hierarchies):
        columns = super(ParticipantReport, self).value_columns(hierarchies)

        # not associated with hierarchy, but vary with metadata/values
        ssnm = SsnmReport()
        columns += ssnm.report_values()
        return columns
