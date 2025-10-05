"""作者快捷按钮管理组件"""
import os
import json
from PyQt6.QtWidgets import QPushButton, QWidget, QSizePolicy
from PyQt6.QtCore import Qt, QEvent

from ...utils.i18n import _
from ...utils.paths import APP_DATA_FILE
from ..layouts import JustifyFlowLayout


class CreatorButtonsMixin:
    """作者按钮管理功能混入类"""
    
    def init_creator_buttons(self):
        """初始化作者按钮相关变量"""
        self.creator_buttons = []
        self.max_creator_buttons = 8
        self.pinned_creator_buttons = set()
        self.pinned_creator_buttons_order = []
        self._load_pinned_creators()
    
    def setup_creator_buttons_ui(self, container: QWidget):
        """设置作者按钮UI容器
        
        Args:
            container: QWidget容器，需要已设置固定高度105px
        """
        self.creator_buttons_container = container
        self.creator_buttons_layout = JustifyFlowLayout(container)
        self.creator_buttons_layout.setSpacing(8)
    
    def on_creator_info_detected(self, creator_info: dict):
        """处理检测到的作者信息，创建快捷按钮"""
        if not creator_info or not creator_info.get('name'):
            return
        
        current_url = self.url_input.text().strip()
        
        try:
            if os.path.exists(APP_DATA_FILE):
                with open(APP_DATA_FILE, "r", encoding='utf-8') as f:
                    app_data = json.load(f)
            else:
                app_data = {"settings": self.settings, "creator_buttons": [], "version": "1.0.0"}
            
            creator_urls = app_data.get('creator_urls', [])
            
            if current_url in creator_urls:
                creator_urls.remove(current_url)
            
            creator_urls.insert(0, current_url)
            creator_urls = creator_urls[:self.max_creator_buttons]
            
            app_data['creator_urls'] = creator_urls
            app_data['creator_info'] = app_data.get('creator_info', {})
            app_data['creator_info'][current_url] = creator_info
            
            with open(APP_DATA_FILE, "w", encoding='utf-8') as f:
                json.dump(app_data, f, ensure_ascii=False, indent=4)
            
            self._refresh_creator_buttons()
            
        except Exception as e:
            print(f"❌ 保存作者URL失败: {e}")
    
    def _refresh_creator_buttons(self):
        """从配置文件重新加载并显示作者按钮"""
        try:
            for button in self.creator_buttons:
                button.setParent(None)
                button.deleteLater()
            self.creator_buttons.clear()
            
            for i in reversed(range(self.creator_buttons_layout.count())):
                item = self.creator_buttons_layout.takeAt(i)
                if item and item.widget():
                    item.widget().setParent(None)
            
            if os.path.exists(APP_DATA_FILE):
                with open(APP_DATA_FILE, "r", encoding='utf-8') as f:
                    app_data = json.load(f)
                
                creator_urls = app_data.get('creator_urls', [])
                creator_info_dict = app_data.get('creator_info', {})
                
                pinned_urls = [url for url in self.pinned_creator_buttons_order if url in creator_urls]
                unpinned_urls = [url for url in creator_urls if url not in self.pinned_creator_buttons]
                
                for url in pinned_urls + unpinned_urls:
                    if url in creator_info_dict:
                        creator_info = creator_info_dict[url]
                        creator_key = f"{creator_info.get('service', '')}_{creator_info.get('id', '')}"
                        self._create_creator_button(creator_info, creator_key)
                
                if self.creator_buttons:
                    self.creator_buttons_container.setVisible(True)
                    self.creator_info_label.setVisible(True)
                    self.creator_info_label.setText(_('creator_info.hover_tip'))
                else:
                    self.creator_info_label.setVisible(False)
                
        except Exception as e:
            print(f"❌ 刷新作者按钮失败: {e}")
    
    def _create_creator_button(self, creator_info: dict, creator_key: str, insert_at_front: bool = False):
        """创建单个作者快捷按钮"""
        service = creator_info.get('service', '').lower()
        name = creator_info.get('name', '')
        post_count = creator_info.get('post_count', 0)
        updated = creator_info.get('updated', '')
        creator_url = creator_info.get('url', '')
        
        button = QPushButton()
        is_pinned = creator_url in self.pinned_creator_buttons
        button.setObjectName("creatorButtonPinned" if is_pinned else "creatorButton")
        button.creator_url = creator_url
        
        display_text = f"⭐ {name}" if is_pinned else name
        button.setText(display_text)
        
        button.setMinimumHeight(30)
        button.setMaximumHeight(35)
        
        font_metrics = button.fontMetrics()
        text_width = font_metrics.boundingRect(display_text).width()
        if hasattr(font_metrics, 'horizontalAdvance'):
            text_width = font_metrics.horizontalAdvance(display_text)
        button_width = text_width + 24
        button.setMinimumWidth(button_width)
        
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        button._creator_service = self._get_service_display_name(service)
        button._creator_post_count = post_count
        button._creator_updated = updated
        
        button.installEventFilter(self)
        button.clicked.connect(lambda: self._on_creator_button_clicked(creator_url))
        button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        button.customContextMenuRequested.connect(lambda pos: self._on_creator_button_right_clicked(button, creator_url))
        
        if insert_at_front:
            self.creator_buttons.insert(0, button)
        else:
            self.creator_buttons.append(button)
        
        self.creator_buttons_layout.addWidget(button)
        return button
    
    def _get_service_display_name(self, service: str) -> str:
        """获取服务的显示名称"""
        service_names = {
            'patreon': 'Patreon',
            'fanbox': 'Fanbox',
            'fantia': 'Fantia',
            'onlyfans': 'OnlyFans',
            'fansly': 'Fansly',
            'boosty': 'Boosty',
            'gumroad': 'Gumroad',
            'subscribestar': 'SubscribeStar'
        }
        return service_names.get(service.lower(), service.title())
    
    def _on_creator_button_clicked(self, creator_url: str):
        """处理作者按钮点击事件"""
        if creator_url:
            self.url_input.setText(creator_url)
    
    def _on_creator_button_right_clicked(self, button: QPushButton, creator_url: str):
        """处理作者按钮右键点击事件，切换固定状态"""
        if not creator_url:
            return
        
        if creator_url in self.pinned_creator_buttons:
            self.pinned_creator_buttons.remove(creator_url)
        else:
            self.pinned_creator_buttons.add(creator_url)
        
        self._save_pinned_creators()
        self._refresh_creator_buttons()
    
    def _save_pinned_creators(self):
        """保存固定的作者按钮状态到配置文件"""
        try:
            try:
                with open(APP_DATA_FILE, 'r', encoding='utf-8') as f:
                    app_data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                app_data = {}
            
            old_pinned = app_data.get('pinned_creators', [])
            new_pinned = [url for url in self.pinned_creator_buttons if url not in old_pinned]
            updated_pinned = new_pinned + [url for url in old_pinned if url in self.pinned_creator_buttons]
            
            self.pinned_creator_buttons_order = updated_pinned
            app_data['pinned_creators'] = updated_pinned
            
            with open(APP_DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(app_data, f, ensure_ascii=False, indent=2)
            
        except Exception as e:
            pass  # 静默处理错误
    
    def _load_pinned_creators(self):
        """从配置文件加载固定的作者按钮状态"""
        try:
            with open(APP_DATA_FILE, 'r', encoding='utf-8') as f:
                app_data = json.load(f)
                
            pinned_list = app_data.get('pinned_creators', [])
            self.pinned_creator_buttons_order = pinned_list
            self.pinned_creator_buttons = set(pinned_list)
            
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            self.pinned_creator_buttons_order = []
            self.pinned_creator_buttons = set()
        except Exception as e:
            print(f"❌ 加载固定状态失败: {e}")
            self.pinned_creator_buttons_order = []
            self.pinned_creator_buttons = set()
    
    def _show_creator_info(self, button):
        """显示作者详细信息"""
        service = getattr(button, '_creator_service', '')
        post_count = getattr(button, '_creator_post_count', 0)
        updated = getattr(button, '_creator_updated', '')
        
        info_lines = []
        if service:
            info_lines.append(service)
        if post_count > 0:
            current_lang = self.settings.get("language", "zh_CN")
            if current_lang == "en_US":
                info_lines.append(f"Posts: {post_count}")
            else:
                info_lines.append(f"帖子数: {post_count}")
        if updated:
            try:
                from datetime import datetime
                updated_dt = datetime.fromisoformat(updated.replace('Z', '+00:00'))
                updated_str = updated_dt.strftime('%Y-%m-%d')
                current_lang = self.settings.get("language", "zh_CN")
                if current_lang == "en_US":
                    info_lines.append(f"Last Updated: {updated_str}")
                else:
                    info_lines.append(f"最后更新: {updated_str}")
            except:
                updated_str = updated[:10] if len(updated) >= 10 else updated
                if updated_str:
                    current_lang = self.settings.get("language", "zh_CN")
                    if current_lang == "en_US":
                        info_lines.append(f"Last Updated: {updated_str}")
                    else:
                        info_lines.append(f"最后更新: {updated_str}")
        
        info_text = ' | '.join(info_lines) if info_lines else ""
        self.creator_info_label.setText(info_text)
    
    def _hide_creator_info(self):
        """隐藏作者详细信息"""
        self.creator_info_label.setText(_('creator_info.hover_tip'))

