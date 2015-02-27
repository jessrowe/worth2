from django import forms
from django.db import models

from worth2.main.generic.models import BasePageBlock


class ProtectiveBehaviorsResults(BasePageBlock):
    quiz_class = models.CharField(max_length=255, help_text='Required',
                                  default='protective-behaviors')
    display_name = 'Protective Behaviors Results'
    template_file = 'protectivebehaviors/protective_behaviors_results.html'

    def needs_submit(self):
        return False

    def unlocked(self, user):
        return True

    def __unicode__(self):
        return "%s -- %s" % (unicode(self.pageblock()), self.quiz_category)

    @staticmethod
    def add_form():
        return ProtectiveBehaviorsResultsForm()

    def edit_form(self):
        return ProtectiveBehaviorsResultsForm(instance=self)

    @staticmethod
    def create(request):
        form = ProtectiveBehaviorsResultsForm(request.POST)
        return form.save()

    def edit(self, vals, files):
        form = ProtectiveBehaviorsResultsForm(
            data=vals, files=files, instance=self)
        if form.is_valid():
            form.save()


class ProtectiveBehaviorsResultsForm(forms.ModelForm):
    class Meta:
        model = ProtectiveBehaviorsResults
