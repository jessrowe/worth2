define([
    'jquery',
    'views/create-participant',
    'views/edit-participant',
    'views/sign-in-participant',
    'views/sign-out-participant',
    'views/manage-participant-filter',
    'views/sign-in-participant-filter',
    'views/goal-setting-form',
    'views/goal-checkin-form',
    'views/locked-video',
    'views/self-talk-road',
    'views/unlocker',
    'views/quiz-validator',
    'jquery-cookie'
], function(
    $,
    CreateParticipantView, EditParticipantView, SignInParticipantView,
    SignOutParticipantView,
    ManageParticipantFilter, SignInParticipantFilter, GoalSettingFormView,
    GoalCheckinFormView, LockedVideo, SelfTalkRoad, Unlocker, QuizValidator
) {
    $(function() {
        var csrftoken = $.cookie('csrftoken');
        function csrfSafeMethod(method) {
            // these HTTP methods do not require CSRF protection
            return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
        }
        $.ajaxSetup({
            beforeSend: function(xhr, settings) {
                if (!csrfSafeMethod(settings.type) && !this.crossDomain) {
                    xhr.setRequestHeader('X-CSRFToken', csrftoken);
                }
            }
        });
    });
    var initialize = function() {
        new CreateParticipantView();
        $('form.worth-edit-participant').each(function() {
            new EditParticipantView({
                el: $(this)
            });
        });

        new SignInParticipantView();

        new SignOutParticipantView();

        new ManageParticipantFilter();

        new SignInParticipantFilter();

        new GoalSettingFormView();

        new GoalCheckinFormView();

        new LockedVideo();

        new SelfTalkRoad();

        new Unlocker();

        new QuizValidator();
    };

    return {
        initialize: initialize
    };
});
