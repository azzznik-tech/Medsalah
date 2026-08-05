[app]
# © 2026 med asava - All rights reserved
title = بحث الأفلام والترجمات
package.name = salahbot
package.domain = org.salahbot

icon.filename = icon.png

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf

version = 1.0

# المكتبات المطلوبة (بايثون + Kivy + بدون تليجرام)
requirements = python3==3.11.9,hostpython3==3.11.9,kivy,requests

orientation = portrait
fullscreen = 0

# صلاحيات أندرويد المطلوبة (اتصال إنترنت + حفظ ملفات الترجمة على الجهاز)
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE

# نسخة أندرويد المستهدفة
android.api = 33
android.minapi = 24
android.ndk_api = 24

# المعماريات المدعومة
android.archs = arm64-v8a, armeabi-v7a

[buildozer]
log_level = 2
warn_on_root = 1
