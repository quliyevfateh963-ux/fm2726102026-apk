[app]
title = FM27(26.10.2026)
package.name = fm2726102026
package.domain = org.hobi
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,txt,ttf
version = 1.0
requirements = python3,kivy,pygame
orientation = landscape
fullscreen = 0
icon.filename = %(source.dir)s/icon.png
presplash.filename = %(source.dir)s/presplash.png
android.permissions = INTERNET
android.api = 33
android.minapi = 21
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
