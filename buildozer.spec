[app]
title = Смена
package.name = smena
package.domain = org.smena
source.dir = .
source.include_exts = py
version = 0.1
requirements = python3,kivy==2.3.0,cython
orientation = landscape
fullscreen = 1

# Android
android.api = 34
android.minapi = 21
android.archs = arm64-v8a
android.accept_sdk_license = True
android.allow_backup = True
android.ndk = 25b

[buildozer]
log_level = 2
warn_on_root = 1
