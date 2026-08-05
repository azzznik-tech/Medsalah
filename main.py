"""
تطبيق البحث عن الأفلام والمسلسلات وتحميل ترجماتها — مستقل تماماً، بدون تليجرام.

# © 2026 med asava - All rights reserved
"""

import os
import threading
import traceback

from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

bot_logic = None
IMPORT_ERROR = None
try:
    import bot_logic
except Exception:
    IMPORT_ERROR = traceback.format_exc()


def _get_downloads_dir():
    """يرجّع مجلد قابل للكتابة لحفظ الترجمات — يجرب مجلد التنزيلات العام أولاً."""
    candidates = [
        "/storage/emulated/0/Download",
        "/sdcard/Download",
    ]
    for path in candidates:
        if os.path.isdir(path) and os.access(path, os.W_OK):
            return path
    # احتياطي: مجلد التطبيق الخاص (يشتغل دايم بدون صلاحيات)
    try:
        from android.storage import app_storage_path
        path = app_storage_path()
        os.makedirs(path, exist_ok=True)
        return path
    except Exception:
        return os.getcwd()


class MovieSubsApp(App):
    def build(self):
        self.title = "بحث الأفلام والترجمات"

        if IMPORT_ERROR:
            return self._error_screen(IMPORT_ERROR)

        try:
            return self._build_ui()
        except Exception:
            return self._error_screen(traceback.format_exc())

    # ─── شاشة عرض الأخطاء (احتياطية) ───
    def _error_screen(self, message):
        root = BoxLayout(orientation="vertical", padding=10, spacing=10)
        root.add_widget(Label(text="حدث خطأ — صوّر هذي الشاشة:", size_hint=(1, 0.08)))
        error_label = Label(text=message, size_hint_y=None, halign="left", valign="top", font_size="12sp")
        error_label.bind(texture_size=self._update_scroll_height)
        scroll = ScrollView(size_hint=(1, 0.92))
        scroll.add_widget(error_label)
        root.add_widget(scroll)
        return root

    # ─── الواجهة الرئيسية ───
    def _build_ui(self):
        root = BoxLayout(orientation="vertical", padding=15, spacing=10)

        search_row = BoxLayout(size_hint=(1, 0.08), spacing=8)
        self.search_input = TextInput(
            hint_text="اكتب اسم الفيلم أو المسلسل...",
            multiline=False,
            size_hint=(0.75, 1),
        )
        self.search_input.bind(on_text_validate=self.on_search)
        search_btn = Button(text="بحث", size_hint=(0.25, 1))
        search_btn.bind(on_press=self.on_search)
        search_row.add_widget(self.search_input)
        search_row.add_widget(search_btn)
        root.add_widget(search_row)

        self.status_label = Label(text="اكتب اسم فيلم وابدأ البحث", size_hint=(1, 0.06), font_size="13sp")
        root.add_widget(self.status_label)

        # منطقة معلومات الفيلم
        self.info_label = Label(
            text="", size_hint_y=None, halign="left", valign="top", font_size="13sp"
        )
        self.info_label.bind(texture_size=self._update_scroll_height)
        info_scroll = ScrollView(size_hint=(1, 0.35))
        info_scroll.add_widget(self.info_label)
        root.add_widget(info_scroll)

        # قائمة الترجمات (أزرار ديناميكية)
        root.add_widget(Label(text="الترجمات المتوفرة:", size_hint=(1, 0.05), font_size="13sp"))
        self.subs_list = BoxLayout(orientation="vertical", size_hint_y=None, spacing=6)
        self.subs_list.bind(minimum_height=self.subs_list.setter("height"))
        subs_scroll = ScrollView(size_hint=(1, 0.46))
        subs_scroll.add_widget(self.subs_list)
        root.add_widget(subs_scroll)

        self._current_subtitles = []
        self._current_title = ""
        return root

    def _update_scroll_height(self, instance, size):
        instance.height = size[1]
        instance.text_size = (instance.width, None)

    def _set_status(self, text):
        Clock.schedule_once(lambda dt: setattr(self.status_label, "text", text))

    def _set_info(self, text):
        Clock.schedule_once(lambda dt: setattr(self.info_label, "text", text))

    # ─── البحث ───
    def on_search(self, instance):
        query = self.search_input.text.strip()
        if not query:
            return
        self._set_status("جاري البحث...")
        self._set_info("")
        Clock.schedule_once(lambda dt: self._clear_subs_list())
        threading.Thread(target=self._search_thread, args=(query,), daemon=True).start()

    def _clear_subs_list(self):
        self.subs_list.clear_widgets()

    def _search_thread(self, query):
        year_match = bot_logic.YEAR_PATTERN.search(query)
        year = int(year_match.group(0)) if year_match else None
        clean_query = bot_logic.YEAR_PATTERN.sub("", query).strip()

        # ─── TMDB ───
        movie_title = clean_query
        try:
            results = bot_logic.tmdb_search(clean_query)
        except Exception as e:
            self._set_status(f"تعذر الاتصال بـ TMDB: {e}")
            return

        if results:
            item = results[0]
            info_text = bot_logic.format_movie_info(item)
            self._set_info(info_text)
            movie_title = item.get("title") or item.get("name") or clean_query
            year = bot_logic.extract_year(item) or year
        else:
            self._set_info("لم يتم العثور على معلومات لهذا العمل.")

        self._current_title = movie_title

        # ─── SubSource ───
        self._set_status("جاري البحث عن الترجمات...")
        try:
            movies = bot_logic.subsource_search(movie_title, year=year)
        except Exception as e:
            self._set_status(f"تعذر الاتصال بـ SubSource: {e}")
            return

        if not movies:
            self._set_status("لم أجد هذا العمل بقاعدة الترجمات.")
            return

        movie_id = movies[0].get("movieId")
        if not movie_id:
            self._set_status("تعذر تحديد معرّف العمل.")
            return

        try:
            subtitles = bot_logic.subsource_get_subtitles(movie_id, language="arabic")
        except Exception as e:
            self._set_status(f"تعذر جلب الترجمات: {e}")
            return

        if not subtitles:
            self._set_status("لا توجد ترجمة عربية متاحة لهذا العمل.")
            return

        self._current_subtitles = subtitles
        self._set_status(f"وجدت {len(subtitles)} ترجمة — اختر واحدة بالأسفل")
        Clock.schedule_once(lambda dt: self._populate_subs_list(subtitles))

    def _populate_subs_list(self, subtitles):
        self.subs_list.clear_widgets()
        for i, sub in enumerate(subtitles[:20]):
            label = bot_logic.format_subtitle_label(sub, i)
            btn = Button(text=label, size_hint_y=None, height=45)
            btn.bind(on_press=lambda inst, idx=i: self.on_pick_subtitle(idx))
            self.subs_list.add_widget(btn)

    # ─── تحميل الترجمة ───
    def on_pick_subtitle(self, index):
        if index >= len(self._current_subtitles):
            return
        sub = self._current_subtitles[index]
        sub_id = sub.get("subtitleId")
        if not sub_id:
            self._set_status("معرّف الترجمة غير موجود.")
            return
        self._set_status("جاري تحميل الترجمة...")
        threading.Thread(target=self._download_thread, args=(sub_id,), daemon=True).start()

    def _download_thread(self, sub_id):
        try:
            raw = bot_logic.subsource_download(sub_id)
        except Exception as e:
            self._set_status(f"فشل التحميل: {e}")
            return

        if not raw:
            self._set_status("التحميل أعاد بيانات فارغة.")
            return

        srt_data, filename = bot_logic.extract_srt(raw, fallback_name=self._current_title or "subtitle")
        safe_name = "".join(c for c in filename if c not in '\\/:*?"<>|')

        try:
            save_dir = _get_downloads_dir()
            save_path = os.path.join(save_dir, safe_name)
            with open(save_path, "wb") as f:
                f.write(srt_data)
            self._set_status(f"تم الحفظ: {save_path}")
        except Exception as e:
            self._set_status(f"فشل حفظ الملف: {e}")


if __name__ == "__main__":
    try:
        MovieSubsApp().run()
    except Exception:
        _tb = traceback.format_exc()
        try:
            from jnius import autoclass
            from android.runnable import run_on_ui_thread

            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            AlertDialogBuilder = autoclass("android.app.AlertDialog$Builder")
            activity = PythonActivity.mActivity

            @run_on_ui_thread
            def _show():
                builder = AlertDialogBuilder(activity)
                builder.setTitle("خطأ")
                builder.setMessage(str(_tb)[:4000])
                builder.setCancelable(False)
                builder.show()

            _show()
        except Exception:
            pass
        try:
            with open("/sdcard/moviesubs_crash.txt", "w", encoding="utf-8") as f:
                f.write(_tb)
        except Exception:
            pass
