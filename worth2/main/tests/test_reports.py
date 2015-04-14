import datetime
from django.core.cache import cache
from django.core.urlresolvers import reverse
from django.test.testcases import TestCase
from pagetree.models import Hierarchy, Section, UserPageVisit
from pagetree.tests.factories import ModuleFactory

from worth2.main.reports import ParticipantReport
from worth2.main.tests.factories import (EncounterFactory, ParticipantFactory,
                                         UserFactory)


class ParticipantReportTest(TestCase):

    def setUp(self):
        super(ParticipantReportTest, self).setUp()
        cache.clear()

        self.participant = ParticipantFactory().user
        self.participant2 = ParticipantFactory().user
        self.staff = UserFactory(is_superuser=True)

        ModuleFactory("main", "/pages/")
        self.hierarchy = Hierarchy.objects.get(name='main')

    def test_get_users(self):
        section_one = Section.objects.get(slug='one')
        UserPageVisit.objects.create(user=self.participant,
                                     section=section_one,
                                     status="complete")
        self.assertEquals(ParticipantReport(self.hierarchy).users().count(), 1)

    def test_encounter_id(self):
        report = ParticipantReport(self.hierarchy)
        the_participant = self.participant.profile.participant
        the_participant.cohort_id = '333'
        the_participant.save()

        # modules one
        module = Section.objects.get(slug='one')
        child = Section.objects.get(slug='introduction')

        # no encounters
        self.assertIsNone(report.encounter_id(the_participant, 0, module, 0))

        # regular encounter
        e1 = EncounterFactory(participant=the_participant,
                              section=module)
        # makeup encounter
        e2 = EncounterFactory(participant=the_participant,
                              section=child, session_type='makeup')

        eid = report.encounter_id(the_participant, 0, module, 0)
        self.assertEquals(eid[0:3], '333')
        self.assertEquals(eid[3:4], '1')  # module index
        self.assertEquals(int(eid[4:9]), e1.facilitator.id)
        self.assertEquals(eid[9:19], e1.created_at.strftime("%y%m%d%I%M"))
        self.assertEquals(eid[19:20], '0')
        self.assertEquals(int(eid[20:22]), e1.location.id)

        # makeup encounter
        eid = report.encounter_id(the_participant, 0, module, 1)
        self.assertEquals(eid[0:3], '333')
        self.assertEquals(eid[3:4], '1')  # module index
        self.assertEquals(int(eid[4:9]), e2.facilitator.id)
        self.assertEquals(eid[9:19], e2.created_at.strftime("%y%m%d%I%M"))
        self.assertEquals(eid[19:20], '1')
        self.assertEquals(int(eid[20:22]), e2.location.id)

        self.assertIsNone(report.encounter_id(the_participant, 0, module, 2))

    def test_percent_complete(self):
        report = ParticipantReport(self.hierarchy)
        root = self.hierarchy.get_root()

        pct = report.percent_complete(self.participant, root)
        self.assertEquals(pct, 0)

        # visit section one & child one
        section_one = Section.objects.get(slug='one')
        child_one = Section.objects.get(slug='introduction')
        UserPageVisit.objects.create(
            user=self.participant, section=section_one, status="complete")
        UserPageVisit.objects.create(
            user=self.participant, section=child_one, status="complete")
        pct = report.percent_complete(self.participant, root)
        self.assertAlmostEquals(pct, 50.0)

    def test_modules_completed(self):
        report = ParticipantReport(self.hierarchy)
        section_one = Section.objects.get(slug='one')
        child_one = Section.objects.get(slug='introduction')

        count = report.modules_completed(self.participant)
        self.assertEquals(count, 0)

        UserPageVisit.objects.create(
            user=self.participant, section=section_one, status="complete")
        UserPageVisit.objects.create(
            user=self.participant, section=child_one, status="complete")
        count = report.modules_completed(self.participant)
        self.assertEquals(count, 1)

        section_two = Section.objects.get(slug='two')
        UserPageVisit.objects.create(
            user=self.participant, section=section_two,
            status="complete")
        count = report.modules_completed(self.participant)
        self.assertEquals(count, 2)

        section_four = Section.objects.get(slug='four')
        UserPageVisit.objects.create(
            user=self.participant, section=section_four,
            status="complete")
        count = report.modules_completed(self.participant)
        self.assertEquals(count, 3)

    def test_time_spent(self):
        report = ParticipantReport(self.hierarchy)

        module_one = Section.objects.get(slug='one')
        time_spent = report.time_spent(self.participant, module_one)
        self.assertEquals(time_spent, "00:00:00")

        now = datetime.datetime.now()
        section_one = Section.objects.get(slug='one')
        child_one = Section.objects.get(slug='introduction')

        visit = UserPageVisit.objects.create(
            user=self.participant, section=section_one, status="complete")
        delta = datetime.timedelta(minutes=-60)
        visit.first_visit = now + delta
        visit.save()

        visit = UserPageVisit.objects.create(
            user=self.participant, section=child_one, status="complete")
        delta = datetime.timedelta(minutes=-46)
        visit.first_visit = now + delta
        visit.save()

        time_spent = report.time_spent(self.participant, module_one)
        self.assertEquals(time_spent, "00:14:00")

        delta = datetime.timedelta(minutes=-25)
        visit.first_visit = now + delta
        visit.save()

        time_spent = report.time_spent(self.participant, module_one)
        self.assertEquals(time_spent, "00:05:00")

    def test_metadata(self):
        rows = [
            ['hierarchy', 'itemIdentifier', 'exercise type', 'itemType',
             'itemText', 'answerIdentifier', 'answerText'],
            '',
            ['', 'study_id', 'profile', 'string', 'Randomized Study Id'],
            ['', 'cohort_id', 'profile', 'string', 'Assigned Cohort Id'],
            ['', 'modules_completed', 'profile', 'count', 'modules completed'],
            ['', '0_time_spent', 'profile', 'string', 'One Time Spent'],
            ['', '0_encounter', 'profile', 'string', 'One Encounter'],
            ['', '0_first_makeup', 'profile', 'string', 'One First Makeup'],
            ['', '0_second_makeup', 'profile', 'string', 'One Second Makeup'],
            ['', '1_time_spent', 'profile', 'string', 'Two Time Spent'],
            ['', '1_encounter', 'profile', 'string', 'Two Encounter'],
            ['', '1_first_makeup', 'profile', 'string', 'Two First Makeup'],
            ['', '1_second_makeup', 'profile', 'string', 'Two Second Makeup'],
            ['', '2_time_spent', 'profile', 'string', 'Four Time Spent'],
            ['', '2_encounter', 'profile', 'string', 'Four Encounter'],
            ['', '2_first_makeup', 'profile', 'string', 'Four First Makeup'],
            ['', '2_second_makeup', 'profile', 'string', 'Four Second Makeup']
        ]

        report = ParticipantReport(self.hierarchy)
        metadata = report.metadata(Hierarchy.objects.all())
        for row in rows:
            self.assertEquals(metadata.next(), row)

        with self.assertRaises(StopIteration):
            metadata.next()

    def test_values(self):
        rows = [
            ['study_id', 'cohort_id', 'modules_completed', '0_time_spent',
             '0_encounter', '0_first_makeup', '0_second_makeup',
             '1_time_spent', '1_encounter', '1_first_makeup',
             '1_second_makeup', '2_time_spent', '2_encounter',
             '2_first_makeup', '2_second_makeup']
        ]

        report = ParticipantReport(self.hierarchy)
        values = report.values(Hierarchy.objects.all())

        for row in rows:
            self.assertEquals(values.next(), row)

        with self.assertRaises(StopIteration):
            values.next()

    def test_post(self):
        report_url = reverse('participant-report')
        # not logged in
        response = self.client.post(report_url)
        self.assertEquals(response.status_code, 302)

        # logged in
        self.client.login(username=self.staff.username, password="test")
        data = {'report_type': 'keys'}
        response = self.client.post(report_url, data)
        self.assertEquals(response.status_code, 200)