require.config({
    shim: {
        bootstrap: {
            deps: ['jquery']
        },
        jquery: {
            exports: '$'
        },
        'jquery-cookie': {
            deps: ['jquery']
        },
        backbone: {
            deps: ['underscore', 'jquery'],
            exports: 'Backbone'
        },
        underscore: {
            exports: '_'
        },
        threejs: {
            exports: 'THREE'
        },
        tweenjs: {
            exports: 'TWEEN'
        }
    },
    paths: {
        bootstrap: '//netdna.bootstrapcdn.com/bootstrap/3.3.2/js/bootstrap.min',
        jquery: '../lib/jquery',
        'jquery-cookie': '../lib/jquery.cookie',
        underscore: '../lib/underscore',
        backbone: '../lib/backbone',
        threejs: '../lib/three.min',
        tweenjs: '../lib/tween.min'
    },
    urlArgs: 'bust=' + (new Date()).getTime()
});

require([
    'app'
], function(App) {
    App.initialize();
});
