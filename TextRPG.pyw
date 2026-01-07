import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import json
import random
import os
import sys
from collections import Counter

# ===== 데이터 =====
# 현재 실행 파일 기준으로 data 폴더 경로 설정
if getattr(sys, 'frozen', False):
    # PyInstaller 등으로 패키징된 실행 파일(.exe)에서 실행 중일 때
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # 일반 파이썬 스크립트로 실행 중일 때
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

def load_json(filename):
    path = os.path.join(DATA_DIR, filename)
    with open(path, encoding="utf-8") as f:
        return json.load(f)

# JSON 불러오기
DUNGEONS = load_json("dungeons.json")
MONSTERS = load_json("monsters.json")
# shop.json은 부위별로 나뉜 딕셔너리 구조로 유지합니다.
SHOP_BY_SLOT = load_json("shop.json")
# 평탄화된 리스트도 생성(하위 항목에 '부위' 필드 추가)
SHOP_ITEMS = []
for slot, items in SHOP_BY_SLOT.items():
    for it in items:
        entry = dict(it)
        entry["부위"] = slot if slot != "소모품" else None
        SHOP_ITEMS.append(entry)

JOB_SKILLS = load_json("skills.json")
# 직업별 스킬 매핑을 JSON에서 불러옵니다 (data/jobs.json)
try:
    JOBS = load_json("jobs.json")
except Exception:
    JOBS = {}

# ===== 설정 로드 (config.json) =====
try:
    CONFIG = load_json("config.json")
except Exception:
    # 파일이 없을 경우를 대비한 최소한의 기본값
    CONFIG = {
        'ui': {'colors': {}, 'fonts': {'main': '맑은 고딕'}},
        'player': {'base_hp': 100, 'base_atk': 15, 'base_next_exp': 100},
        'game_rules': {'skill_auto_cast_prob': 0.3},
        'enhance': {'base_cost': 100, 'multiplier': 1.5, 'penalties': {}},
        'enhance_probabilities': {},
        'difficulty_badges': {},
        'difficulty_colors': {'없음':'#ffffff'},
        'difficulty_scale': {'없음':1},
        'difficulty_reward_bonus': {'없음':0.0}
    }

# ===== 강화 관련 유틸/설정 =====
# config 내의 강화 관련 값을 읽어오는 헬퍼. 모든 강화 관련 하드코딩을 제거하고
# 게임 밸런스는 data/config.json에서 관리할 수 있도록 설계했습니다.
ENHANCE_CFG = CONFIG.get('enhance', {})
ENHANCE_BASE_COST = ENHANCE_CFG.get('base_cost', 100)
ENHANCE_MULTIPLIER = ENHANCE_CFG.get('multiplier', 1.5)
ENHANCE_PENALTIES = ENHANCE_CFG.get('penalties', {})
ENHANCE_PROBS = CONFIG.get('enhance_probabilities', {'0-5':{'min':100,'max':100}, '6-10':{'min':50,'max':80}, '11-20':{'min':10,'max':40}})

def enhance_cost_for_level(cur_level):
    """현재 강화 레벨(cur_level)에서 다음 단계(+1)를 시도할 때 필요한 골드를 반환합니다.
    규칙: +1 시도(레벨 L -> L+1)의 비용 = base_cost * multiplier ** L
    예: L=0 -> 100, L=1 -> 150, L=2 -> 225 ...
    """
    return int(round(ENHANCE_BASE_COST * (ENHANCE_MULTIPLIER ** cur_level)))

def enhance_success_chance(cur_level):
    """현재 레벨(cur_level)에 대한 성공 확률을 CONFIG의 enhance_probabilities에서 계산합니다.
    범위 키(예: '0-5')를 찾아서 min~max 사이의 랜덤 퍼센트 값을 반환합니다.
    """
    lvl = cur_level
    for k, v in ENHANCE_PROBS.items():
        if '-' in k:
            lo, hi = [int(x) for x in k.split('-',1)]
            if lo <= lvl <= hi:
                mn, mx = v.get('min', 0), v.get('max', 0)
                if mn == mx:
                    return mn / 100.0
                return random.randint(mn, mx) / 100.0
    # 기본 안전값
    return 0.1


# 던전별 몬스터 매핑
dungeon_map = {d["던전명"]: [] for d in DUNGEONS}
for m in MONSTERS:
    dungeon_map[m["던전"]].append(m)

# 난이도 배지 매핑 (config에서 가져오기)
DIFFICULTY_BADGES = CONFIG.get('difficulty_badges', {})
# 던전 난이도별 기본 색상 (레벨/클리어에 따라 변형 가능)
DIFFICULTY_COLORS = CONFIG.get('difficulty_colors', {})
# 난이도별 레벨당 증가 퍼센트 (클리어 11~20 단계를 기준으로 적용)
DIFFICULTY_SCALE = CONFIG.get('difficulty_scale', {})
# 던전 보상 배수(기본 난이도에 따른 EXP/Gold 보정)
DIFFICULTY_REWARD_BONUS = CONFIG.get('difficulty_reward_bonus', {})


def stage_by_clears(clears):
    """클리어 수에 따라 화면에 표시될 난이도 단계를 반환합니다.
    0-10: 없음(흰색), 11-12: 초급, 13-14: 중급, 15-16: 상급, 17+: 보스
    """
    if clears <= 10:
        return '없음'
    if 11 <= clears <= 12:
        return '초급'
    if 13 <= clears <= 14:
        return '중급'
    if 15 <= clears <= 16:
        return '상급'
    return '보스'


def badge_for(dname):
    diff = next((d.get('난이도') for d in DUNGEONS if d.get('던전명') == dname), '없음')
    return DIFFICULTY_BADGES.get(diff, '⚪')

# 던전별 보상 매핑 (JSON에서 가져오기)
REWARDS = {d["던전명"]: d["보상"] for d in DUNGEONS}

def make_quest():
    monster = random.choice(MONSTERS)
    count = random.randint(1, 5)
    reward = REWARDS.get(monster["던전"], 20)
    return {
        "목표": f"{monster['이름']} 처치",
        "수량": count,
        "진행": 0,
        "완료": False,
        "보상": reward
    }

# 유틸: 값 제한
def clamp(val, low, high):
    return max(low, min(high, val))

# 퀘스트 리스트 생성
QUESTS = [make_quest() for _ in range(5)]

# ===== 플레이어 =====
class Player:
    def __init__(self, name, job, hp=None, atk=None):
        self.name, self.job = name, job
        # 기본 스탯 설정 (config 참조)
        cfg = CONFIG.get('player', {})
        self.lv = 1
        self.max_hp = hp if hp is not None else cfg.get('base_hp', 100)
        self.hp = self.max_hp  # 현재 HP
        self.atk = atk if atk is not None else cfg.get('base_atk', 15)
        self.exp = 0
        self.next_exp = cfg.get('base_next_exp', 100)
        self.gold = 0

        self.inv, self.skills = ["포션"], []
        self.running = False
        self.quest_index = 0
        self.quest = QUESTS[self.quest_index] if QUESTS else None
        self.defense_buff = 0  # 다음 적 공격에 대해 경감할 임시 방어력
        # 장착 아이템 슬롯(투구, 갑옷, 장갑, 신발, 무기, 방패)
        self.equipped = {"투구": None, "갑옷": None, "장갑": None, "신발": None, "무기": None, "방패": None}
        # 아이템별 강화 레벨(예: {'강철검': 3})
        self.enhancements = {}
        self.buffs = []  # 활성화된 버프 목록

    def level_up(self, log):
        cfg = CONFIG.get('player', {})
        while self.exp >= self.next_exp:
            self.lv += 1
            self.exp -= self.next_exp
            # 레벨업 시 스탯 증가량 적용
            self.max_hp += cfg.get('levelup_hp_inc', 30)
            self.hp = self.max_hp   # 레벨업 시 체력 회복
            self.atk += cfg.get('levelup_atk_inc', 7)
            self.next_exp += cfg.get('levelup_exp_inc', 50)
            # 레벨업 메시지는 노란색 볼드로 표시
            log(f"🎉 레벨업! Lv {self.lv} | HP {self.hp} | ATK {self.atk}", "level_up")

    def heal_full(self, log):
        self.hp = self.max_hp
        log("🏠 마을에서 휴식! HP 완전 회복!", "green")

    def get_attack(self):
        bonus = 0
        for slot, name in self.equipped.items():
            if name:
                entry = next((e for e in SHOP_ITEMS if e.get('이름') == name), None)
                if entry:
                    lvl = self.enhancements.get(name, 0)
                    bonus += entry.get('공격력', 0) + lvl
        # 버프 적용
        for b in self.buffs:
            if b.get('type') == 'atk':
                bonus += b.get('amount', 0)
        return self.atk + bonus

    def get_defense(self):
        bonus = 0
        for slot, name in self.equipped.items():
            if name:
                entry = next((e for e in SHOP_ITEMS if e.get('이름') == name), None)
                if entry:
                    lvl = self.enhancements.get(name, 0)
                    bonus += entry.get('방어력', 0) + lvl
        # 버프 적용
        for b in self.buffs:
            if b.get('type') == 'def':
                bonus += b.get('amount', 0)
        return bonus

    def tick_buffs(self, log):
        # 턴 종료 시 버프 지속시간 감소 및 만료 처리
        active = []
        for b in self.buffs:
            b['duration'] -= 1
            if b['duration'] > 0:
                active.append(b)
            else:
                log(f"📉 {b['name']} 효과가 사라졌습니다.", "white")
        self.buffs = active
        
# ===== 툴팁 클래스 =====
class ToolTip:
    def __init__(self, widget, text_provider):
        self.widget = widget
        self.text_provider = text_provider
        self.tip_window = None
        self.widget.bind("<Enter>", self.show_tip)
        self.widget.bind("<Leave>", self.hide_tip)
        self.widget.bind("<Motion>", self.move_tip)

    def show_tip(self, event=None):
        text = self.text_provider()
        if not text: return
        if self.tip_window: return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=text, justify="left",
                         background="#2b2b2b", foreground="#ffffff",
                         relief="solid", borderwidth=1,
                         font=("맑은 고딕", 9))
        label.pack(ipadx=4, ipady=2)

    def hide_tip(self, event=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None

    def move_tip(self, event):
        if self.tip_window:
            x = event.x_root + 15
            y = event.y_root + 15
            self.tip_window.wm_geometry(f"+{x}+{y}")

# ===== 메인 앱 =====
class RPGApp:
    def __init__(self, root):
        self.root = root
        ui_cfg = CONFIG.get('ui', {})
        colors = ui_cfg.get('colors', {})
        
        root.title(ui_cfg.get('window_title', "Dark Text RPG"))
        # 전체적인 테마: 조금 더 부드러운 다크 톤으로 변경
        root.configure(bg=colors.get('bg_root', "#0f1720"))

        # 공용 버튼/스타일 설정 (config에서 로드)
        self.MAIN_BTN_BG = colors.get('btn_main', "#2e86de")
        self.MAIN_BTN_HOVER_BG = colors.get('btn_main_hover', "#54a0ff")
        self.SECOND_BTN_BG = "#1f2937" # 보조 버튼 (현재 미사용이나 유지)
        self.RED_BTN_BG = colors.get('btn_red', "#c62828")
        self.RED_BTN_HOVER_BG = colors.get('btn_red_hover', "#e53935")
        self.BORDER_COLOR = colors.get('border', "#444444")
        
        self.base_font_size = 12
        self.reduced_font_size = max(9, int(self.base_font_size * 0.85))
        self.btn_font = ("맑은 고딕", self.reduced_font_size, "bold")
        self.btn_width = 6
        self.btn_height = 2

        self.player = None
        self.inv_window, self.shop_window, self.equip_window = None, None, None
        # 던전 클리어 카운트 저장 (던전 난이도 상승 트래킹)
        self.dungeon_clears = {}
        self.make_character_dialog()

        # -----------------------------
        # 창 중앙 배치 함수
        # -----------------------------
    def center_window(self, w, h):
        self.root.deiconify()   # 숨겨둔 root 창 다시 표시
        self.root.update_idletasks()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        x, y = (sw - w)//2, (sh - h)//2
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        # 메인 창 크기 조절 불가로 고정
        self.root.resizable(False, False)
        
        # 기존 위젯 초기화 (재진입 시 중복 방지)
        for widget in self.root.winfo_children():
            if isinstance(widget, tk.Toplevel): continue
            widget.destroy()

        # -----------------------------
        # 상단 정보 (여러 라벨로 표시)
        # -----------------------------
        ui_cfg = CONFIG.get('ui', {})
        colors = ui_cfg.get('colors', {})

        bg_panel = colors.get('bg_panel', "#1c1c1c")
        bg_list = colors.get('bg_list', "#121212")
        
        # 전체 컨테이너
        main_frame = tk.Frame(self.root, bg=colors.get('bg_root'))
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # [1] 상단 상태창 (STATUS)
        status_frame = tk.LabelFrame(main_frame, text=" STATUS ", bg=bg_panel, fg="#888", font=("맑은 고딕", 9, "bold"), bd=1, relief="solid")
        status_frame.pack(fill="x", pady=(0, 8))

        # 상태 정보 그리드
        # Row 0: 기본 정보
        self.name_label = tk.Label(status_frame, text="이름: -", fg="cyan", bg=bg_panel, font=("맑은 고딕", 10, "bold"))
        self.job_label = tk.Label(status_frame, text="직업: -", fg="orange", bg=bg_panel, font=("맑은 고딕", 10))
        self.lv_label = tk.Label(status_frame, text="Lv: -", fg="lightblue", bg=bg_panel, font=("맑은 고딕", 10))
        self.gold_label = tk.Label(status_frame, text="Gold: -", fg="gold", bg=bg_panel, font=("맑은 고딕", 10))
        
        self.name_label.grid(row=0, column=0, padx=10, pady=2, sticky="w")
        self.job_label.grid(row=0, column=1, padx=10, pady=2, sticky="w")
        self.lv_label.grid(row=0, column=2, padx=10, pady=2, sticky="w")
        self.gold_label.grid(row=0, column=3, padx=10, pady=2, sticky="w")

        # Row 1: 게이지 바 (HP, EXP)
        gauge_frame = tk.Frame(status_frame, bg=bg_panel)
        gauge_frame.grid(row=1, column=0, columnspan=4, sticky="ew", padx=5, pady=2)
        
        tk.Label(gauge_frame, text="HP", fg="#ff6b6b", bg=bg_panel, font=("맑은 고딕", 9)).pack(side="left")
        self.hp_bar = tk.Canvas(gauge_frame, width=200, height=14, bg="#0b1113", highlightthickness=0)
        self.hp_bar.pack(side="left", padx=(5, 15))
        
        tk.Label(gauge_frame, text="EXP", fg="#feca57", bg=bg_panel, font=("맑은 고딕", 9)).pack(side="left")
        self.exp_bar = tk.Canvas(gauge_frame, width=200, height=14, bg="#0b1113", highlightthickness=0)
        self.exp_bar.pack(side="left", padx=5)

        # Row 2: 퀘스트 및 스킬
        self.quest_label = tk.Label(status_frame, text="퀘스트: -", fg=colors.get('text_highlight'), bg=bg_panel, font=("맑은 고딕", 10))
        self.quest_label.grid(row=2, column=0, columnspan=2, padx=10, pady=(2,6), sticky="w")
        
        self.skill_label = tk.Label(status_frame, text="스킬: -", fg="#98fb98", bg=bg_panel, font=("맑은 고딕", 10))
        self.skill_label.grid(row=2, column=2, columnspan=2, padx=10, pady=(2,6), sticky="w")
        
        # Row 3: 버프 상태
        self.buff_label = tk.Label(status_frame, text="버프: -", fg="#ff79c6", bg=bg_panel, font=("맑은 고딕", 10))
        self.buff_label.grid(row=3, column=0, columnspan=4, padx=10, pady=(0,6), sticky="w")
        
        # 더미 라벨들 (update_info 호환용)
        self.hp_label = tk.Label(self.root) 
        self.exp_label = tk.Label(self.root)

        # -----------------------------
        # 중앙 레이아웃 (던전 리스트 + 버튼)
        # -----------------------------
        center_frame = tk.Frame(main_frame, bg=colors.get('bg_root'))
        center_frame.pack(fill="both", expand=True)

        # [2] 좌측 패널 (던전 목록 + 조작)
        left_panel = tk.Frame(center_frame, bg=colors.get('bg_root'), width=320)
        left_panel.pack(side="left", fill="y", padx=(0, 8))

        # 2-1. 던전 목록 (DUNGEONS)
        dungeon_frame = tk.LabelFrame(left_panel, text=" DUNGEONS ", bg=bg_panel, fg="#888", font=("맑은 고딕", 9, "bold"), bd=1, relief="solid")
        dungeon_frame.pack(fill="x", pady=(0, 8))

        # 난이도 순으로 정렬하고, 2열(왼쪽/오른쪽)으로 배치합니다.
        difficulty_order = {'없음':0, '초급':1, '중급':2, '상급':3, '보스':4}
        sorted_dungeons = sorted(DUNGEONS, key=lambda d: (difficulty_order.get(d.get('난이도'), 2), d.get('던전명')))
        # 이름만 표시하고 배지는 제거
        names = [d['던전명'] for d in sorted_dungeons]

        # 두 열로 분할 (왼쪽 위에서 아래로 먼저 채움)
        mid = (len(names) + 1) // 2
        left_names = names[:mid]
        right_names = names[mid:]

        list_container = tk.Frame(dungeon_frame, bg=bg_list)
        list_container.pack(fill="x", padx=5, pady=5)
        lb_font = ("맑은 고딕", 10)
        # 명시적 width로 리스트 크기 고정 (버튼과 정렬되도록) 및 수직으로 채우기
        list_width = 20
        self.dungeon_list_left = tk.Listbox(list_container, width=list_width, height=8, bg=bg_list, fg="#e6eef3", font=lb_font, exportselection=False, bd=0, highlightthickness=0)
        self.dungeon_list_right = tk.Listbox(list_container, width=list_width, height=8, bg=bg_list, fg="#e6eef3", font=lb_font, exportselection=False, bd=0, highlightthickness=0)
        self.dungeon_list_left.pack(side="left", padx=(0,6), fill="y")
        self.dungeon_list_right.pack(side="left", padx=(6,0), fill="y")

        def _display_and_color_for(name):
            # 클리어 수에 따른 표시 단계 및 색상 결정
            lvl = self.dungeon_clears.get(name, 0)
            stage = stage_by_clears(lvl)
            # 항상 횟수를 표기
            display = f"{name} ({lvl})"
            color = DIFFICULTY_COLORS.get(stage, '#ffffff')
            return display, color

        def refresh_dungeon_list():
            # 리스트를 재구성하여 카운트/색상을 갱신
            self.dungeon_list_left.delete(0, tk.END)
            self.dungeon_list_right.delete(0, tk.END)
            mid = (len(names) + 1) // 2
            left_names = names[:mid]
            right_names = names[mid:]
            for name in left_names:
                display, color = _display_and_color_for(name)
                self.dungeon_list_left.insert(tk.END, display)
                try:
                    idx = self.dungeon_list_left.size() - 1
                    self.dungeon_list_left.itemconfig(idx, foreground=color)
                except Exception:
                    pass
            for name in right_names:
                display, color = _display_and_color_for(name)
                self.dungeon_list_right.insert(tk.END, display)
                try:
                    idx = self.dungeon_list_right.size() - 1
                    self.dungeon_list_right.itemconfig(idx, foreground=color)
                except Exception:
                    pass
        # 초기 호출
        refresh_dungeon_list()
        self.refresh_dungeon_list = refresh_dungeon_list

        # 선택 시 다른 열의 선택을 해제하도록 바인딩
        def _sync_clear(other):
            def fn(event):
                try:
                    other.selection_clear(0, tk.END)
                except Exception:
                    pass
            return fn
        self.dungeon_list_left.bind('<<ListboxSelect>>', _sync_clear(self.dungeon_list_right))
        self.dungeon_list_right.bind('<<ListboxSelect>>', _sync_clear(self.dungeon_list_left))

        # 던전 이름 표시에서 괄호 표기 '(+N)'을 제거하여 내부 던전명만 반환
        def _strip_badge(display_name):
            # 형식: "던전명 (N)" 또는 "던전명 (+N)" 또는 "던전명"
            # 괄호 표기가 있으면 뒤쪽 괄호를 제거하여 내부 던전명만 반환
            if ' (' in display_name and display_name.endswith(')'):
                return display_name.rsplit(' (', 1)[0]
            return display_name
        self._strip_badge = _strip_badge
        # 반복 횟수 입력 (입장 시 지정한 횟수만큼 연속 클리어 시도)
        repeat_frame = tk.Frame(dungeon_frame, bg=bg_panel)
        repeat_frame.pack(pady=(0,5), padx=5, fill="x")
        tk.Label(repeat_frame, text="반복", fg="#aaa", bg=bg_panel, font=lb_font).pack(side="left", padx=(0,6))
        vcmd_digits = (self.root.register(lambda v: v.isdigit() or v == ""), '%P')
        # 반복 입력 필드: 리스트와 동일한 폰트/비율로 확장
        self.repeat_entry = tk.Entry(repeat_frame, width=6, validate='key', validatecommand=vcmd_digits, font=lb_font, bg=bg_list, fg="white", insertbackground="white")
        self.repeat_entry.insert(0, '1')
        self.repeat_entry.pack(side="left")
        # 진행 게이지 및 중지 버튼 (반복 횟수 입력 우측 배치)
        style = ttk.Style()
        try:
            style.theme_use('default')
        except Exception:
            pass
        style.configure("Repeat.Horizontal.TProgressbar", troughcolor="#222", background=self.MAIN_BTN_BG, thickness=12)
        self.repeat_pbar = ttk.Progressbar(repeat_frame, orient='horizontal', length=80, mode='determinate', style="Repeat.Horizontal.TProgressbar")
        self.repeat_pbar.pack(side='left', padx=(8,6))
        self.repeat_label = tk.Label(repeat_frame, text='', fg='white', bg=bg_panel, font=("맑은 고딕", 9))
        self.repeat_label.pack(side='left', padx=(0,6))
        
        # 입장/중지 버튼: 크기 20% 축소 (width 10->8, height 2->1로 조정하여 컴팩트하게)
        small_w, small_h = 6, 1
        
        # 입장 버튼 (반복 프레임으로 이동)
        btn_enter = tk.Button(repeat_frame, text="입 장", bg=self.MAIN_BTN_BG, fg="white",
                  font=("맑은 고딕", 9, "bold"), width=small_w, height=small_h,
                  relief="flat", bd=0,
                  command=self.enter_selected)
        btn_enter.pack(side="left", padx=(0,4))

        # 중지 버튼
        self.repeat_stop_btn = tk.Button(repeat_frame, text='중지', bg=self.MAIN_BTN_BG, fg='white', font=("맑은 고딕", 9, "bold"), width=small_w, height=small_h, relief='flat', bd=0, command=self.stop_repeats, state='disabled')
        self.repeat_stop_btn.pack(side='left')

        def on_blue_hover(e):
            if e.widget['state'] != 'disabled':
                e.widget['bg'] = self.MAIN_BTN_HOVER_BG
        def on_blue_leave(e):
            e.widget['bg'] = self.MAIN_BTN_BG
        
        for b in (btn_enter, self.repeat_stop_btn):
            b.bind("<Enter>", on_blue_hover)
            b.bind("<Leave>", on_blue_leave)

        # 2-2. 기능 버튼 (ACTIONS) - 그리드 배열로 변경
        action_frame = tk.LabelFrame(left_panel, text=" ACTIONS ", bg=bg_panel, fg="#888", font=("맑은 고딕", 9, "bold"), bd=1, relief="solid")
        action_frame.pack(fill="x")

        # 버튼 그리드 컨테이너
        btn_grid = tk.Frame(action_frame, bg=bg_panel)
        btn_grid.pack(padx=5, pady=5, fill="x")

        # 기능 버튼들: 2열 그리드로 배치
        func_btns = [
            ("인벤토리", self.open_inventory, 0, 0),
            ("상 점", self.open_shop, 0, 1),
            ("장 비", self.open_equipment, 1, 0),
            ("퀘스트", self.show_quest, 1, 1),
            ("마을 휴식", self.rest_in_town, 2, 0) # 휴식은 2칸 차지하거나 단독
        ]

        def on_btn_hover(e):
            e.widget['bg'] = self.RED_BTN_HOVER_BG
        def on_btn_leave(e):
            e.widget['bg'] = self.RED_BTN_BG

        for txt, cmd, r, c in func_btns:
            btn = tk.Button(btn_grid, text=txt, bg=self.RED_BTN_BG, fg="white",
                      font=self.btn_font, height=2,
                      relief="flat", bd=0,
                      command=cmd)
            # 휴식 버튼은 가로로 꽉 차게 (span 2)
            if txt == "마을 휴식":
                btn.grid(row=r, column=c, columnspan=2, padx=2, pady=2, sticky="ew")
            else:
                btn.grid(row=r, column=c, padx=2, pady=2, sticky="ew")
            
            btn.bind("<Enter>", on_btn_hover)
            btn.bind("<Leave>", on_btn_leave)
            
        btn_grid.columnconfigure(0, weight=1)
        btn_grid.columnconfigure(1, weight=1)

        # -----------------------------
        # 오른쪽 레이아웃 (로그창)
        # -----------------------------
        right_panel = tk.LabelFrame(center_frame, text=" LOGS ", bg=bg_panel, fg="#888", font=("맑은 고딕", 9, "bold"), bd=1, relief="solid")
        right_panel.pack(side="left", fill="both", expand=True)

        self.title_label = tk.Label(right_panel, text="마을",
                            font=("맑은 고딕", 11, "bold"),
                            fg=colors.get('text_highlight', "#dbeafe"), bg=bg_panel)
        self.title_label.pack(fill="x", pady=(4,4))

        # 로그창을 위아래로 분할: 위는 전투 메시지 전용, 아래는 기타 메시지 전용
        log_frame = tk.Frame(right_panel, bg=bg_panel)
        log_frame.pack(fill="both", expand=True, padx=5, pady=5)

        self.combat_box = tk.Text(log_frame, width=60, height=10,
                                  bg=colors.get('bg_log_combat', "#071122"), fg=colors.get('text_main', "#e6eef3"), bd=0,
                                  highlightbackground=self.BORDER_COLOR, highlightthickness=1)
        self.combat_box.pack(fill="both", expand=True, pady=(0,5))

        self.general_box = tk.Text(log_frame, width=60, height=8,
                                   bg=colors.get('bg_log_general', "#0b1113"), fg=colors.get('text_main', "#e6eef3"), bd=0,
                                   highlightbackground=self.BORDER_COLOR, highlightthickness=1)
        self.general_box.pack(fill="x", expand=False)

        # 태그 설정을 두 창 모두에 적용
        for box in (self.combat_box, self.general_box):
            box.tag_config("player_attack", foreground="deepskyblue", justify="left")   # 내 공격
            box.tag_config("enemy_attack", foreground="red", justify="right")   # 적 공격
            box.tag_config("yellow", foreground="yellow", justify="left")       # 스킬 발동 등
            box.tag_config("white", foreground="white", justify="left")         # 일반 메시지
            box.tag_config("bold_item", foreground="white", font=("맑은 고딕", 10, "bold"))
            box.tag_config("level_up", foreground="yellow", font=("맑은 고딕", 10, "bold"))
            box.tag_config("dungeon_entry", foreground="white", font=("맑은 고딕", 11, "bold"))
            for tag,color in [("deepskyblue","cyan"),("red","red"),("yellow","yellow"),("green","lightgreen"),("white","white")]:
                box.tag_config(tag, foreground=color)

        # 하위 호환을 위해 기존 변수 명 유지(기존 코드가 log_box를 참조할 경우 대비)
        self.log_box = self.general_box
        
    def center_toplevel(self, win, w, h):
        """주어진 Toplevel 창을 화면 중앙으로 이동시키고 크기 조절을 금지합니다."""
        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        x, y = (sw - w)//2, (sh - h)//2
        win.geometry(f"{w}x{h}+{x}+{y}")
        win.resizable(False, False)

    # 캐릭터 선택 (개선된 레이아웃) 
    def make_character_dialog(self):
        win = tk.Toplevel(self.root)
        win.title("⚔️ Dark Text RPG 캐릭터 생성")
        
        # Config 로드
        ui_cfg = CONFIG.get('ui', {})
        colors = ui_cfg.get('colors', {})
        bg_root = colors.get('bg_root', "#1c1c1c")
        bg_panel = colors.get('bg_panel', "#1c1c1c")
        bg_list = colors.get('bg_list', "#121212")
        text_main = colors.get('text_main', "white")
        
        win.configure(bg=bg_root)

        # 고정 크기 창 (중앙 정렬 및 크기 고정)
        w, h = 420, 280
        self.center_toplevel(win, w, h)
        win.grab_set()
        
        # Combobox 스타일 설정 (다크 테마)
        try:
            style = ttk.Style()
            style.theme_use('default')
            style.configure('TCombobox', fieldbackground=bg_list, background=bg_panel, foreground=text_main, arrowcolor=text_main)
            style.map('TCombobox', fieldbackground=[('readonly', bg_list)], selectbackground=[('readonly', self.MAIN_BTN_BG)], selectforeground=[('readonly', 'white')])
        except Exception:
            pass

        label_font = ("맑은 고딕", 11, "bold")
        entry_font = ("맑은 고딕", 11)

        # 메인 화면과 통일된 디자인 (LabelFrame 사용)
        frame = tk.LabelFrame(win, text=" CHARACTER ", bg=bg_panel, fg="#888", font=("맑은 고딕", 9, "bold"), bd=1, relief="solid")
        frame.pack(expand=True, fill="both", padx=20, pady=20)

        # 내부 컨텐츠 정렬을 위한 그리드 컨테이너
        inner = tk.Frame(frame, bg=bg_panel)
        inner.pack(expand=True)

        # 이름 입력 검증 함수 (메서드 안에 정의해야 self 사용 가능)
        def validate_name(new_value):
            # 한글만 입력된 경우 → 최대 8글자
            if all('가' <= ch <= '힣' for ch in new_value):
                return len(new_value) <= 8
            # 영어만 입력된 경우 → 최대 10글자
            if all(ch.isalpha() and 'A' <= ch.upper() <= 'Z' for ch in new_value):
                return len(new_value) <= 10
            # 혼합된 경우 → 영어 기준(10글자)
            return len(new_value) <= 10

        vcmd = (self.root.register(validate_name), "%P")

        # 이름 입력칸
        tk.Label(inner, text="이름", fg=text_main, bg=bg_panel, font=label_font)\
            .grid(row=0, column=0, padx=10, pady=15, sticky="e")
        name_entry = tk.Entry(inner, bg=bg_list, fg="white", font=entry_font,
                              width=18, validate="key", validatecommand=vcmd, 
                              relief="flat", insertbackground="white")
        name_entry.grid(row=0, column=1, padx=10, pady=15)

        # 직업 선택
        tk.Label(inner, text="직업", fg=text_main, bg=bg_panel, font=label_font)\
            .grid(row=1, column=0, padx=10, pady=(15, 5), sticky="e")
        job_box = ttk.Combobox(inner, values=list(JOBS.keys()), font=entry_font, width=16, state="readonly")
        job_box.grid(row=1, column=1, padx=10, pady=(15, 5))
        job_box.current(0)

        # 직업 설명 (기본 스킬 표시)
        desc_label = tk.Label(inner, text="", fg="#aaa", bg=bg_panel, font=("맑은 고딕", 9))
        desc_label.grid(row=2, column=0, columnspan=2, sticky="n", pady=(0, 10))

        def update_job_desc(event=None):
            job = job_box.get()
            skills = JOBS.get(job, [])
            if skills:
                desc_label.config(text=f"기본 스킬: {', '.join(skills)}")
            else:
                desc_label.config(text="기본 스킬 없음")
        
        job_box.bind("<<ComboboxSelected>>", update_job_desc)
        update_job_desc() # 초기 실행

        # 초기 스탯 주사위 굴리기
        stats_frame = tk.Frame(inner, bg=bg_panel)
        stats_frame.grid(row=3, column=0, columnspan=2, pady=5)
        
        p_cfg = CONFIG.get('player', {})
        base_hp = p_cfg.get('base_hp', 100)
        base_atk = p_cfg.get('base_atk', 15)
        dialog_state = {'hp': base_hp, 'atk': base_atk}

        stats_label = tk.Label(stats_frame, text=f"HP: {base_hp}  |  ATK: {base_atk}", 
                               fg="#feca57", bg=bg_panel, font=("맑은 고딕", 11, "bold"))
        stats_label.pack(side="left", padx=10)

        def roll_dice():
            # 랜덤 범위: HP -10~+20, ATK -2~+5
            new_hp = base_hp + random.randint(-10, 20)
            new_atk = base_atk + random.randint(-2, 5)
            dialog_state['hp'] = new_hp
            dialog_state['atk'] = new_atk
            stats_label.config(text=f"HP: {new_hp}  |  ATK: {new_atk}", fg="#ff79c6")

        roll_btn = tk.Button(stats_frame, text="🎲 주사위", bg=self.SECOND_BTN_BG, fg="white",
                             font=("맑은 고딕", 9), relief="flat", command=roll_dice)
        roll_btn.pack(side="left")

        # 확인 버튼
        def confirm():
            name = name_entry.get().strip() or "용사"
            job = job_box.get()
            self.player = Player(name, job, hp=dialog_state['hp'], atk=dialog_state['atk'])
            win.destroy()  # 캐릭터 생성창 닫기

            # 메인창 띄우기
            self.center_window(900, 600)
            self.switch_view("town")

            # 이제 라벨이 있으므로 안전하게 갱신 가능
            self.update_info()
            self.log(f"🧝 캐릭터 생성: {self.player.name} ({self.player.job})", "white")

        btn = tk.Button(inner, text="모험 시작", bg=self.MAIN_BTN_BG, fg="white", font=("맑은 고딕", 11, "bold"),
                  width=14, height=1, relief="flat", bd=0,
                  command=confirm)
        btn.grid(row=4, column=0, columnspan=2, pady=20)
        
        # 버튼 호버 효과
        def on_enter(e): e.widget['bg'] = self.MAIN_BTN_HOVER_BG
        def on_leave(e): e.widget['bg'] = self.MAIN_BTN_BG
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
 
    # 로그 출력 메서드
    def log(self, text, tag="white"):
        # 로그창이 준비되지 않은 경우 콘솔 출력으로 대체
        if not hasattr(self, 'general_box') or not isinstance(self.general_box, tk.Text):
            try:
                print(text)
            except Exception:
                pass
            return
        # 전투 관련 태그는 상단 전투창에, 그 외 메시지는 하단 일반창에 표시
        combat_tags = ("player_attack", "enemy_attack")
        if tag in combat_tags and hasattr(self, 'combat_box'):
            box = self.combat_box
        else:
            box = self.general_box
        box.config(state="normal")
        box.insert(tk.END, text + "\n", tag)
        box.see(tk.END)
        box.config(state="disabled")    
 
    # 정보/게이지 갱신
    def update_info(self):
        p = self.player
        if not p:
            return
        # 초기화가 끝나기 전에 호출될 수 있으므로 레이블 존재 여부를 체크
        if not hasattr(self, 'name_label'):
            return

        # 스킬 문자열
        skills_text = ", ".join(p.skills) if p.skills else "-"

        # 퀘스트 문자열
        if hasattr(p, "quest") and p.quest:
            q = p.quest
            quest_text = f"{q['목표']} {q['진행']}/{q['수량']}"
        else:
            quest_text = "퀘스트 없음"

        # 라벨 갱신
        self.name_label.config(text=f"🧝 이름: {p.name}")
        self.job_label.config(text=f"⚔️ 직업: {p.job}")
        self.lv_label.config(text=f"Lv: {p.lv}")
        self.gold_label.config(text=f"💰 Gold: {p.gold}")
        self.skill_label.config(text=f"✨ 스킬: {skills_text}")
        self.quest_label.config(text=f"📜 {quest_text}")
        
        # 버프 상태 표시
        if hasattr(self, 'buff_label'):
            if p.buffs:
                buff_list = []
                for b in p.buffs:
                    icon = "⚔️" if b.get('type') == 'atk' else "🛡️"
                    buff_list.append(f"{icon} {b.get('name')}({b.get('duration')}턴)")
                buff_str = " | ".join(buff_list)
            else:
                buff_str = "없음"
            self.buff_label.config(text=f"🔥 버프: {buff_str}")

        # 게이지바 갱신 (내부에 현재/최대 값을 텍스트로 표시)
        self.hp_bar.delete("all")
        hp_ratio = p.hp / p.max_hp if p.max_hp else 0
        self.hp_bar.create_rectangle(0, 0, 200 * hp_ratio, 20, fill="#ff6b6b", outline="")
        try:
            self.hp_bar.create_text(100, 8, text=f"{p.hp}/{p.max_hp}", fill='white', font=("맑은 고딕", 8, "bold"))
        except Exception:
            pass

        self.exp_bar.delete("all")
        exp_ratio = p.exp / p.next_exp if p.next_exp else 0
        self.exp_bar.create_rectangle(0, 0, 200 * exp_ratio, 20, fill="#feca57", outline="")
        try:
            self.exp_bar.create_text(100, 8, text=f"{p.exp}/{p.next_exp}", fill='#111', font=("맑은 고딕", 8, "bold"))
        except Exception:
            pass

    # 뷰 전환
    def switch_view(self, view):
        if view == "town":
            if hasattr(self, 'title_label'):
                self.title_label.config(text="마을")
            self.log("🏠 마을입니다. 휴식/퀘스트/상점 버튼을 이용하세요.", "white")
        else:
            if hasattr(self, 'title_label'):
                self.title_label.config(text=f"현재 던전: {view}")

    # 입장(자동 전투 시작)
    def enter_selected(self):
        if not self.player or self.player.running: return
        # 선택된 던전은 왼쪽/오른쪽 리스트 중 하나에서 가져옵니다
        sel_left = self.dungeon_list_left.curselection() if hasattr(self, 'dungeon_list_left') else ()
        sel_right = self.dungeon_list_right.curselection() if hasattr(self, 'dungeon_list_right') else ()
        if not sel_left and not sel_right:
            self.log("⚠ 던전을 선택하세요.", "white"); return
        if sel_left:
            disp = self.dungeon_list_left.get(sel_left[0])
        else:
            disp = self.dungeon_list_right.get(sel_right[0])
        name = self._strip_badge(disp)
        if name == "마을":
            self.switch_view("town")
            return
        # 반복 횟수(입장 전에 지정한 값)를 읽음
        try:
            val = int(self.repeat_entry.get())
            val = max(1, val)
        except Exception:
            val = 1
        # 반복 관련 상태 초기화
        self.repeat_total_runs = val
        self.repeat_completed = 0
        self.requested_runs_remaining = val - 1
        # enable stop button and update UI
        try:
            self.repeat_stop_btn.configure(state='normal')
            self.repeat_entry.config(state='disabled')
            self._update_repeat_progress()
        except Exception:
            pass
        self.switch_view(name)
        self.player.running = True
        # 입장 메시지는 현재 클리어 기반 단계 색상으로 표시
        # config에 정의된 색상을 사용하여 난이도별 입장 로그 색상 적용
        lvl = self.dungeon_clears.get(name, 0)
        stage = stage_by_clears(lvl)
        tag = f"dungeon_stage_{stage}"
        # 태그가 없으면 생성(일반창 테그로 생성)
        try:
            self.general_box.tag_config(tag, foreground=DIFFICULTY_COLORS.get(stage, '#ffffff'))
        except Exception:
            pass
        self.log(f"🏰 {name} 입장!", tag)
        self.root.after(80, lambda: self.run_dungeon(name, 0))

    def stop_repeats(self):
        # 중지 버튼: 현재 진행을 멈추고 추가 입장을 차단
        self.requested_runs_remaining = 0
        # ensure repeat_total_runs == repeat_completed to make logic stop
        try:
            self.repeat_total_runs = getattr(self, 'repeat_completed', 0)
            self._update_repeat_progress()
            self.repeat_stop_btn.configure(state='disabled')
            self.repeat_entry.config(state='normal')
            self.log("⛔ 반복 입장을 중지했습니다.", "white")
        except Exception:
            pass

    def _update_repeat_progress(self):
        # 진행도를 게이지/라벨로 갱신
        total = getattr(self, 'repeat_total_runs', 0) or 0
        done = getattr(self, 'repeat_completed', 0) or 0
        if total <= 0:
            self.repeat_pbar['value'] = 0
            self.repeat_label.config(text='')
            return
        pct = int((done / total) * 100)
        self.repeat_pbar['value'] = pct
        self.repeat_label.config(text=f"{done}/{total}")

    # 나가기(전투 종료)
    def exit_dungeon(self):
        if self.player:
            self.player.running = False
            self.log("🚪 전투를 종료하고 마을로 돌아갑니다.", "white")
            self.switch_view("town")
            self.update_info()

    # 마을 휴식
    def rest_in_town(self):
        if self.title_label.cget("text") == "마을":
            self.player.heal_full(self.log)
            self.update_info()
        else:
            self.log("❌ 던전에서는 휴식할 수 없습니다.", "red")

    # 퀘스트 확인/완료 처리
    def show_quest(self):
        p = self.player
        if not p.quest:
            self.log("📜 퀘스트 없음", "white")
            return
        q = p.quest
        self.log(f"📜 퀘스트: {q['목표']} {q['진행']}/{q['수량']}", "white")
        if q["진행"] >= q["수량"] and not q["완료"]:
            q["완료"] = True
            p.gold += 50
            self.log("🎉 퀘스트 완료! 보상 50G 지급", "green")
            p.quest_index += 1
            if p.quest_index < len(QUESTS):
                p.quest = QUESTS[p.quest_index]
                self.log(f"➡ 다음 퀘스트: {p.quest['목표']}", "white")
            else:
                p.quest = None
                self.log("✅ 모든 퀘스트 완료! 퀘스트 없음", "white")
            self.update_info()   
    # 던전 루프 (HP 0이 될 때까지 자동 전투)
    def run_dungeon(self, name, idx):
        # 플레이어 상태 확인 및 전투 진행 여부 판단
        p = self.player
        if not p.running: return
        monsters = dungeon_map.get(name, [])
        if p.hp <= 0:
            self.log("💀 쓰러졌습니다. 마을로 귀환합니다.", "white")
            p.running = False
            self.switch_view("town")
            self.update_info()
            try: self.repeat_entry.config(state='normal')
            except: pass
            return
        if idx >= len(monsters):
            # === 던전 클리어 처리 ===
            prev = self.dungeon_clears.get(name, 0)
            now = prev + 1
            self.dungeon_clears[name] = now
            # 보상에 난이도 보너스 적용 (기본 던전 난이도 기준)
            diff = next((d.get('난이도') for d in DUNGEONS if d.get('던전명') == name), '없음')
            reward_bonus = DIFFICULTY_REWARD_BONUS.get(diff, 0.0)
            # 기본 보상 적용
            base_exp = sum(m.get('EXP', 0) for m in monsters)
            base_gold = sum(m.get('골드', 0) for m in monsters)
            exp_gain = int(round(base_exp * (1 + reward_bonus)))
            gold_gain = int(round(base_gold * (1 + reward_bonus)))
            p.exp += exp_gain
            p.gold += gold_gain
            self.log(f"🎉 {name} 클리어! (클리어 횟수: {now}) — 보상: EXP +{exp_gain}, Gold +{gold_gain}", "white")
            # 반복 전투 진행도 갱신
            try:
                self.repeat_completed = getattr(self, 'repeat_completed', 0) + 1
                self._update_repeat_progress()
            except Exception:
                pass
            # 11단계 이상이면 난이도 보정 적용 안내 및 몬스터 강화 알림
            if now > 10:
                per = DIFFICULTY_SCALE.get(diff, 1)
                stages = now - 10
                self.log(f"⚠️ 난이도 보정 적용: {stages}단계 → 몬스터 HP/ATK +{stages * per}%", "white")
            # 던전 리스트 갱신
            try:
                self.refresh_dungeon_list()
            except Exception:
                pass
            # === 자동 재진입 로직 ===
            total = getattr(self, 'repeat_total_runs', 0)
            done = getattr(self, 'repeat_completed', 0)
            if total > 0 and done < total and p.hp > 0 and getattr(self, 'requested_runs_remaining', 0) >= 0:
                # 계속 반복
                # 이전 방식과 호환을 위해 requested_runs_remaining도 감소시킴
                if getattr(self, 'requested_runs_remaining', None) is not None:
                    self.requested_runs_remaining = max(0, getattr(self, 'requested_runs_remaining', 0) - 1)
                self.root.after(80, lambda: self.run_dungeon(name, 0))
                return
            # 반복이 끝났거나 중지됨
            try:
                self.repeat_stop_btn.configure(state='disabled')
                self.repeat_entry.config(state='normal')
            except Exception:
                pass
            p.running = False
            self.switch_view("town")
            self.update_info()
            return

        m = dict(monsters[idx])
        # 던전 클리어 레벨에 따른 스탯 보정 적용
        clears = self.dungeon_clears.get(name, 0)
        if clears > 10:
            eff = min(20, clears)
            stages = eff - 10
            diff = next((d.get('난이도') for d in DUNGEONS if d.get('던전명') == name), '없음')
            per = DIFFICULTY_SCALE.get(diff, 1)
            total_pct = stages * per
            m['HP'] = int(round(m['HP'] * (1 + total_pct / 100.0)))
            m['공격력'] = int(round(m['공격력'] * (1 + total_pct / 100.0)))
        self.log(f"👾 {m['이름']} 등장! (HP {m['HP']}, ATK {m['공격력']})", "white")
        # 전투 턴 시작 (비동기 호출로 UI 멈춤 방지)
        self.root.after(120, lambda: self.battle_step(name, idx, m))

    # 전투 단계
    def battle_step(self, name, idx, m):
        p = self.player
        # === 플레이어 공격 턴 ===
        # 내 공격 (랜덤 데미지)
        base_atk = p.get_attack() if hasattr(p, 'get_attack') else p.atk
        dmg = random.randint(base_atk - 3, base_atk + 3)   # 공격력 ±3 범위
        if p.skills and random.random() < 0.3:
                skill = random.choice(p.skills)
                # 스킬 정의에서 효과를 불러옵니다
                sk = JOB_SKILLS.get(skill, {})
                if sk.get("타입") == "공격":
                    extra = sk.get("공격력", 0)
                    dmg += extra
                    self.log(f"⚡ 스킬 자동 발동: {skill} (추가 피해 +{extra})", "yellow")
                elif sk.get("타입") == "방어":
                    buff = sk.get("방어력", 0)
                    p.defense_buff += buff
                    self.log(f"🛡 스킬 자동 발동: {skill} (방어력 +{buff}, 다음 공격 흡수)", "yellow")
                else:
                    # 알 수 없는 타입이면 기본 +10
                    dmg += 10
                    self.log(f"⚡ 스킬 자동 발동: {skill} (추가 피해 +10)", "yellow")

                # 스킬북/스킬 발동은 강조해서 표시
                self.log(f"(스킬 발동) {skill}", "bold_item")
        m["HP"] -= dmg
        self.log(f"🗡 {p.name} 공격! {m['이름']}에게 {dmg} 데미지 → HP: {m['HP']}", "player_attack")

        # === 몬스터 반격 턴 ===
        if m["HP"] > 0:
            enemy_dmg = random.randint(m["공격력"] - 2, m["공격력"] + 2)  # 공격력 ±2 범위
            # 장착 장비의 방어력(영구 감소)
            equip_def = p.get_defense() if hasattr(p, 'get_defense') else 0
            if equip_def > 0:
                enemy_dmg = max(0, enemy_dmg - equip_def)
                self.log(f"🛡 장비 방어력으로 데미지 {equip_def} 경감 → 현재 데미지: {enemy_dmg}", "white")

            # 방어 버프 적용(한 번만)
            if getattr(p, 'defense_buff', 0) > 0:
                reduced = p.defense_buff
                actual = max(0, enemy_dmg - reduced)
                self.log(f"🛡 {p.name}의 스킬 방어력으로 추가 경감 {reduced} → 실제 데미지: {actual}", "white")
                p.defense_buff = 0
                enemy_dmg = actual

            p.hp -= enemy_dmg
            self.log(f"💢 {m['이름']} 반격! {p.name}에게 {enemy_dmg} 데미지 → HP: {p.hp}", "enemy_attack")
            self.update_info()

            if p.hp <= 0:
                self.log("💀 쓰러졌습니다.", "white")
                p.running = False
                self.root.after(200, self.exit_dungeon)
                return

            # 다음 턴 진행
            p.tick_buffs(self.log)
            self.root.after(220, lambda: self.battle_step(name, idx, m))
            return

        # === 몬스터 처치 및 보상 ===
        self.log(f"🏆 {m['이름']} 처치! EXP +{m['EXP']} | Gold +{m['골드']}", "white")
        p.exp += m["EXP"]
        p.gold += m["골드"]
        p.level_up(self.log)
        if p.quest and m["이름"] in p.quest["목표"]:
            p.quest["진행"] += 1

        # 턴 종료 처리 (버프 시간 감소)
        p.tick_buffs(self.log)

        # === 스킬북 드랍 로직 ===
        # 몬스터별 확률 또는 던전 난이도 기반 기본 확률 사용 (config 참조)
        drops = m.get("드랍스킬", [])
        if drops:
            prob = m.get("스킬북확률")
            if prob is None:
                # 던전 난이도에 따른 기본 확률
                dname = m.get('던전')
                diff = next((d.get('난이도') for d in DUNGEONS if d.get('던전명') == dname), None)
                # config에서 드랍 확률 맵 로드
                prob_map = CONFIG.get('game_rules', {}).get('skill_book_drop_probs', {})
                prob = prob_map.get(diff, 0.06)
            if random.random() < prob:
                drop_skill = random.choice(drops)
                book = f"{drop_skill} 스킬북"
                p.inv.append(book)
                self.log(f"📖 드랍: {book} (확률 {int(prob*100)}%)", "bold_item")
                sk_def = JOB_SKILLS.get(drop_skill)
                if sk_def:
                    self.log(f"📘 드랍 스킬 정보: {drop_skill} (타입: {sk_def.get('타입')}, 공격력: {sk_def.get('공격력',0)}, 방어력: {sk_def.get('방어력',0)})", "white")

        self.update_info()
        self.root.after(300, lambda: self.run_dungeon(name, idx + 1))
    
    # 인벤토리
    def open_inventory(self):
        p = self.player

        # 이미 창이 열려 있으면 새로고침만 실행
        if self.inv_window and tk.Toplevel.winfo_exists(self.inv_window):
            for widget in self.inv_window.winfo_children():
                if isinstance(widget, tk.Listbox):
                    lb = widget
                    lb.delete(0, tk.END)
                    counts = Counter(p.inv)
                    shown = set()
                    for name, cnt in counts.items():
                        entry = next((e for e in SHOP_ITEMS if e.get('이름') == name), None)
                        if entry and entry.get('부위') is None:
                            lb.insert(tk.END, f"{name} x{cnt}")
                            shown.add(name)
                    for item in p.inv:
                        if item in shown:
                            continue
                        lb.insert(tk.END, item)
            self.inv_window.lift()
            self.inv_window.focus_force()
            return

        # 새 창 생성
        win = tk.Toplevel(self.root); self.inv_window = win
        win.title("인벤토리"); win.configure(bg="#1c1c1c")
        self.center_toplevel(win, 320, 300) 

        tk.Label(win, text="아이템 (더블클릭: 사용/장착)", fg="#dbeafe", bg="#1c1c1c", font=("맑은 고딕",11)).pack(pady=18)
        lb = tk.Listbox(win, width=34, height=10, bg="#151515", fg="#e6eef3", font=("맑은 고딕",11))
        lb.pack(padx=18, pady=18, fill="both", expand=True) 

        def refresh():
            lb.delete(0, tk.END)
            counts = Counter(p.inv)
            shown = set()
            # 소모품(부위 None) 집계하여 표시
            for name, cnt in counts.items():
                entry = next((e for e in SHOP_ITEMS if e.get('이름') == name), None)
                if entry and entry.get('부위') is None:
                    lb.insert(tk.END, f"{name} x{cnt}")
                    shown.add(name)
            # 그 외는 개별 항목으로 표시
            for item in p.inv:
                if item in shown:
                    continue
                lb.insert(tk.END, item)
        refresh()

        # === 인벤토리 툴팁 기능 ===
        lb.tip_window = None
        def on_inv_motion(event):
            idx = lb.nearest(event.y)
            bbox = lb.bbox(idx)
            if not bbox:
                hide_inv_tip()
                return
            y_off, _, _, h = bbox
            if not (y_off <= event.y <= y_off + h):
                hide_inv_tip()
                return
            
            raw_text = lb.get(idx)
            # "아이템 xN" 형식 파싱
            if " x" in raw_text and raw_text.rsplit(" x", 1)[1].isdigit():
                name = raw_text.rsplit(" x", 1)[0]
            else:
                name = raw_text
            
            item_data = next((i for i in SHOP_ITEMS if i.get('이름') == name), None)
            if not item_data:
                hide_inv_tip()
                return
            
            info = [f"[{name}]"]
            if item_data.get('부위'): info.append(f"부위: {item_data.get('부위')}")
            else: info.append("타입: 소모품")
            
            if item_data.get('공격력'): info.append(f"⚔️ 공격력: +{item_data.get('공격력')}")
            if item_data.get('방어력'): info.append(f"🛡️ 방어력: +{item_data.get('방어력')}")
            if item_data.get('회복력'): info.append(f"❤️ 회복력: +{item_data.get('회복력')}")
            
            # 강화 레벨 표시
            lvl = p.enhancements.get(name, 0)
            if lvl > 0:
                info.append(f"✨ 강화: +{lvl}")

            text = "\n".join(info)
            
            if lb.tip_window:
                x = event.x_root + 15
                y = event.y_root + 15
                lb.tip_window.wm_geometry(f"+{x}+{y}")
                lbl = lb.tip_window.winfo_children()[0]
                if lbl['text'] != text:
                    lbl['text'] = text
            else:
                tw = tk.Toplevel(lb)
                tw.wm_overrideredirect(True)
                x = event.x_root + 15
                y = event.y_root + 15
                tw.wm_geometry(f"+{x}+{y}")
                label = tk.Label(tw, text=text, justify="left",
                                 background="#2b2b2b", foreground="#ffffff",
                                 relief="solid", borderwidth=1,
                                 font=("맑은 고딕", 9))
                label.pack(ipadx=4, ipady=2)
                lb.tip_window = tw

        def hide_inv_tip(event=None):
            if lb.tip_window:
                lb.tip_window.destroy()
                lb.tip_window = None
        
        lb.bind("<Motion>", on_inv_motion)
        lb.bind("<Leave>", hide_inv_tip)

        # 외부에서 인벤토리 UI를 갱신할 수 있도록 참조 함수 저장
        self._inv_refresh_fn = refresh
        # 장비 창(있다면) 옵션도 최신화
        self.refresh_equipment_options()

        # 더블클릭 이벤트
        def on_double_click(event):
            if not lb.curselection(): return
            raw = lb.get(lb.curselection()[0])

            # consumable 표기인 경우 (예: '포션 x10') 처리
            if ' x' in raw and raw.rsplit(' x',1)[1].isdigit():
                name = raw.rsplit(' x',1)[0]
                entry = next((e for e in SHOP_ITEMS if e.get('이름') == name), None)
                if entry and entry.get('부위') is None:
                    # 소모품 사용 (회복, 버프 등)
                    if name in p.inv:
                        p.inv.remove(name)
                        used_msg = []
                        
                        # 1. 회복
                        if entry.get('회복력'):
                            heal = entry.get('회복력')
                            p.hp = clamp(p.hp + heal, 0, p.max_hp)
                            used_msg.append(f"HP +{heal}")
                        
                        # 2. 공격 버프 (3턴)
                        if entry.get('공격력'):
                            val = entry.get('공격력')
                            p.buffs.append({'type': 'atk', 'amount': val, 'duration': 3, 'name': name})
                            used_msg.append(f"공격력 +{val}(3턴)")

                        # 3. 방어 버프 (3턴)
                        if entry.get('방어력'):
                            val = entry.get('방어력')
                            p.buffs.append({'type': 'def', 'amount': val, 'duration': 3, 'name': name})
                            used_msg.append(f"방어력 +{val}(3턴)")
                        
                        if used_msg:
                            self.log(f"🧪 {name} 사용! " + ", ".join(used_msg), "green")
                        else:
                            self.log(f"🧪 {name} 사용 (효과 없음)", "white")
                            
                        refresh(); self.update_info(); return

            item = raw

            if "스킬북" in item:
                skill = item.replace(" 스킬북","").replace("스킬북","").strip()
                allowed = JOBS.get(p.job, [])
                if skill in allowed:
                    if skill not in p.skills:
                        p.skills.append(skill)
                        self.log(f"✨ 스킬 습득: {skill}", "white")
                    else:
                        self.log(f"ℹ️ 이미 습득한 스킬입니다: {skill}", "white")
                    # 스킬을 배울 수 있으므로 스킬북은 소모
                    p.inv.remove(item)
                    refresh(); self.update_info()
                else:
                    # 해당 직업은 해당 스킬을 배울 수 없음; 스킬북 유지
                    self.log(f"❌ {p.job}은(는) {skill}을(를) 배울 수 없습니다. 스킬북은 유지됩니다.", "red")

            else:
                # 자동 장착 시도: 아이템이 장비 부위에 대응하면 장착 처리
                entry = next((e for e in SHOP_ITEMS if e.get('이름') == item), None)
                if entry and entry.get('부위'):
                    slot = entry.get('부위')
                    prev = p.equipped.get(slot)
                    # 이전 장비가 있으면 인벤토리로 복원
                    if prev and prev != item:
                        if prev not in p.inv:
                            p.inv.append(prev)
                    # 장착 처리
                    p.equipped[slot] = item
                    if item in p.inv:
                        p.inv.remove(item)

                    # 아이템 능력치 메시지 구성
                    stat_parts = []
                    if entry.get('공격력'):
                        stat_parts.append(f"공격력 +{entry.get('공격력')}")
                    if entry.get('방어력'):
                        stat_parts.append(f"방어력 +{entry.get('방어력')}")
                    # 보조적으로 HP 관련 키들을 찾아 표기
                    for hp_key in ('HP', '체력', 'max_hp'):
                        if entry.get(hp_key):
                            stat_parts.append(f"HP +{entry.get(hp_key)}")

                    stats = ", ".join(stat_parts) if stat_parts else "능력치 없음"
                    self.log(f"⚔️ {item} 장착 ({slot}) — {stats}", "bold_item")

                    # UI 동기화
                    refresh(); self.update_info(); self.refresh_equipment_options()
                else:
                    self.log(f"ℹ️ {item}는(은) 사용할 수 없습니다.", "white")

        lb.bind("<Double-Button-1>", on_double_click)

    # 상점
    def open_shop(self):
        if self.shop_window and tk.Toplevel.winfo_exists(self.shop_window):
            self.shop_window.lift(); self.shop_window.focus_force(); return
        win = tk.Toplevel(self.root); self.shop_window = win
        win.title("상점"); win.configure(bg="#1c1c1c")
        # 창을 키워서 내부의 드롭다운과 구매 버튼이 모두 보이도록 함
        self.center_toplevel(win, 560, 420)

        tk.Label(win, text="상점 (드롭다운 → 선택 → 우측 구매)", fg="#dbeafe", bg="#1c1c1c").pack(pady=(10,5))

        shop_frame = tk.Frame(win, bg="#1c1c1c")
        # 좌우/상하 여백을 줄여서 오밀조밀하게 배치
        shop_frame.pack(padx=10, pady=5, fill="both", expand=True) 

        slots = ["무기", "갑옷", "장갑", "투구", "신발", "방패", "소모품"]
        self.shop_widgets = {}

        for idx, slot in enumerate(slots):
            lbl = tk.Label(shop_frame, text=f"{slot}", fg="white", bg="#1c1c1c")
            lbl.grid(row=idx, column=0, sticky="w", pady=4)

            # 해당 부위에 해당하는 상점 아이템 목록 (기타는 부위 없는 아이템)
            options = []
            mapping = {}
            # SHOP_BY_SLOT에서 부위별로 가져옵니다.
            items_for_slot = SHOP_BY_SLOT.get(slot, []) if slot != '기타' else SHOP_BY_SLOT.get('기타', [])
            for e in items_for_slot:
                name = e.get('이름')
                price = e.get('가격', 0)
                disp = f"{name} - {price}G"
                options.append(disp)
                mapping[disp] = (name, price)

            if not options:
                options = ['(없음)']
                mapping = {'(없음)': (None, 0)}

            cb = ttk.Combobox(shop_frame, values=options, state='readonly', width=22)
            cb.set(options[0])
            try:
                cb.configure(foreground='#e6eef3')
            except Exception:
                pass
            cb.grid(row=idx, column=1, padx=6, pady=4, sticky='w')
            
            # 툴팁 연결
            def make_tooltip_provider(c, m):
                def provider():
                    sel = c.get()
                    val = m.get(sel)
                    if not val or not val[0]: return None
                    name = val[0]
                    item_data = next((i for i in SHOP_ITEMS if i.get('이름') == name), None)
                    if not item_data: return None
                    info = [f"[{name}]"]
                    if item_data.get('공격력'): info.append(f"⚔️ 공격력: +{item_data.get('공격력')}")
                    if item_data.get('방어력'): info.append(f"🛡️ 방어력: +{item_data.get('방어력')}")
                    if item_data.get('회복력'): info.append(f"❤️ 회복력: +{item_data.get('회복력')}")
                    return "\n".join(info)
                return provider
            ToolTip(cb, make_tooltip_provider(cb, mapping))
            
            # 수량 선택 스핀박스
            qty_var = tk.IntVar(value=1)
            if slot == "소모품":
                qty_spin = tk.Spinbox(shop_frame, from_=1, to=99, textvariable=qty_var, width=3, font=("맑은 고딕", 10))
            else:
                qty_spin = tk.Spinbox(shop_frame, from_=1, to=1, textvariable=qty_var, width=3, font=("맑은 고딕", 10), state="disabled")
            qty_spin.grid(row=idx, column=2, padx=4, pady=4)

            # 구매 버튼 스타일을 메인 버튼과 동일하게 적용
            buy_btn = tk.Button(shop_frame, text="구매", bg=self.MAIN_BTN_BG, fg="white",
                                font=("맑은 고딕", 11, "bold"), relief="flat", bd=0,
                                width=10, state="disabled", disabledforeground="#94a3b8")
            buy_btn.grid(row=idx, column=3, padx=6, pady=4) 

            # UI 상태 업데이트 (가격 계산 및 버튼 활성화)
            def update_ui_state(c=cb, b=buy_btn, m=mapping, qv=qty_var):
                sel = c.get()
                name_price = m.get(sel)
                if not name_price or not name_price[0]:
                    b.config(state='disabled', text='구매')
                    return
                try:
                    q = int(qv.get())
                    if q < 1: q = 1
                except ValueError:
                    q = 1
                
                name, price = name_price
                total = price * q
                b.config(text=f"구매 ({total}G)")
                # 골드가 부족해도 버튼을 활성화하여 클릭 시 알림을 받을 수 있게 함
                b.config(state='normal')

            # 이벤트 바인딩
            cb.bind('<<ComboboxSelected>>', lambda e, f=update_ui_state: f())
            if slot == "소모품":
                qty_spin.config(command=lambda f=update_ui_state: f())
                qty_spin.bind('<KeyRelease>', lambda e, f=update_ui_state: f())

            # 초기 상태 업데이트
            update_ui_state()

            # 구매 핸들러
            def on_buy_click(c=cb, m=mapping, qv=qty_var):
                sel = c.get()
                name_price = m.get(sel)
                if not name_price or not name_price[0]: return
                try:
                    q = int(qv.get())
                    if q < 1: q = 1
                except ValueError:
                    q = 1
                self.buy_item(name_price[0], name_price[1], q)
                update_ui_state()

            buy_btn.config(command=on_buy_click)
            self.shop_widgets[slot] = (cb, buy_btn, mapping)

        # 장비창 열기 버튼
        # combobox style for shop (modern dark)
        try:
            style = ttk.Style()
            style.theme_use('default')
            style.configure('TCombobox', fieldbackground='#151515', background='#151515', foreground='#e6eef3')
            # ensure readonly state uses visible foreground
            style.map('TCombobox', foreground=[('readonly', '#e6eef3')], fieldbackground=[('readonly', '#151515')])
        except Exception:
            pass


    def open_equipment(self):
        if self.equip_window and tk.Toplevel.winfo_exists(self.equip_window):
            self.equip_window.lift(); self.equip_window.focus_force(); return
        win = tk.Toplevel(self.root); self.equip_window = win
        win.title("장비 장착"); win.configure(bg="#1c1c1c")
        self.center_toplevel(win, 360, 380) 

        tk.Label(win, text="장비 설정", fg="#dbeafe", bg="#1c1c1c", font=("맑은 고딕", 12, "bold")).pack(pady=6)

        frame = tk.Frame(win, bg="#1c1c1c")
        # 상단 여백을 5mm(약 18px)로 맞추고 하단은 최소화
        frame.pack(padx=10, pady=(18,6), fill="both", expand=True)

        slots = ["투구", "갑옷", "장갑", "신발", "무기", "방패"]
        self.equip_widgets = {}

        # 매핑 dict을 초기화합니다 (표시 문자열 -> 실제 아이템명)
        self.equip_mappings = {}
        for idx, slot in enumerate(slots):
            lbl = tk.Label(frame, text=slot, fg="#dbeafe", bg="#1c1c1c", font=("맑은 고딕",11))
            lbl.grid(row=idx, column=0, sticky="w", pady=4)

            # 현재 장착 상태에 따라 표시 문자열에 '(장착됨)'을 붙여 보여줍니다.
            current = self.player.equipped.get(slot) if self.player else None
            # 소유한 아이템(인벤토리 기반) 중 해당 부위 필터
            inv_names = []
            if self.player:
                for name in list(self.player.inv):
                    entry = next((e for e in SHOP_ITEMS if e.get('이름') == name), None)
                    if entry and entry.get('부위') == slot:
                        inv_names.append(name)
            # 현재 장착 중인 아이템은 인벤토리에 없어도 표시(해제 가능해야 함)
            raw_names = inv_names[:]
            if current and current not in raw_names:
                raw_names.append(current)

            display_options = ["(없음)"]
            mapping = {"(없음)": None}
            for name in raw_names:
                disp = f"{name} (장착됨)" if name == current else name
                display_options.append(disp)
                mapping[disp] = name
                # plain name도 매핑해둡니다 (선택의 유연성 확보)
                mapping[name] = name

            cb = ttk.Combobox(frame, values=display_options, state="readonly", width=28)
            # consistent font for visibility
            try:
                cb.config(font=("맑은 고딕",11))
                cb.configure(foreground='#e6eef3')
            except Exception:
                pass
            # 표시 문자열에 강화 레벨을 붙여 표시
            lvl = self.player.enhancements.get(current, 0) if current else 0
            cb_initial = f"{current} +{lvl} (장착됨)" if current and lvl else (f"{current} (장착됨)" if current else "(없음)")
            cb.set(cb_initial)
            cb.grid(row=idx, column=1, pady=4, padx=6, sticky='w')

            # 강화 버튼 추가 (해당 슬롯에 대해 강화 시도)
            def make_enhance_handler(s):
                def on_enhance():
                    self.attempt_enhance(s)
                return on_enhance
            enhance_btn = tk.Button(frame, text="강화", bg=self.MAIN_BTN_BG, fg="white", font=self.btn_font, relief='flat', bd=0, command=make_enhance_handler(slot))
            enhance_btn.grid(row=idx, column=2, padx=6, pady=4) 
            def make_cb_handler(s, combobox):
                def on_selected(event=None):
                    sel_display = combobox.get()
                    actual = self.equip_mappings.get(s, {}).get(sel_display)
                    prev = self.player.equipped.get(s)
                    # Unequip
                    if actual is None:
                        if prev:
                            # prev를 인벤토리에 복원
                            if prev not in self.player.inv:
                                self.player.inv.append(prev)
                            self.player.equipped[s] = None
                            self.log(f"🗑️ {prev} 해제 ({s})", "white")
                    else:
                        # Equip 'actual' and sync inventory
                        if prev and prev != actual:
                            # 이전 장비는 인벤토리에 복원
                            if prev not in self.player.inv:
                                self.player.inv.append(prev)
                        # 실제 장착
                        self.player.equipped[s] = actual
                        # 장착한 아이템은 인벤토리에서 제거(있다면)
                        if actual in list(self.player.inv):
                            self.player.inv.remove(actual)
                        # Show rarity and enhancement level if present
                        level = self.player.enhancements.get(actual, 0) if hasattr(self.player, 'enhancements') else 0
                        rarity = next((e.get('희귀도') for e in SHOP_ITEMS if e.get('이름') == actual), '일반')
                        display_name = f"{actual} +{level}" if level else actual
                        self.log(f"⚔️ {display_name} 장착 ({s}) — 등급: {rarity}", "bold_item")

                    # 선택 후, 해당 콤보의 표시 목록을 갱신하여 '(장착됨)' 표시를 최신화 (인벤토리 기반)
                    new_raw = []
                    for name in list(self.player.inv):
                        entry = next((e for e in SHOP_ITEMS if e.get('이름') == name), None)
                        if entry and entry.get('부위') == s:
                            new_raw.append(name)
                    # current equipped도 포함
                    if self.player.equipped.get(s) and self.player.equipped.get(s) not in new_raw:
                        new_raw.append(self.player.equipped.get(s))

                    new_display = ['(없음)']
                    new_mapping = {'(없음)': None}
                    for n in new_raw:
                        d = f"{n} (장착됨)" if self.player.equipped.get(s) == n else n
                        new_display.append(d)
                        new_mapping[d] = n
                    combobox.config(values=new_display)
                    # set the combobox current shown value to include suffix if equipped
                    cb_cur = f"{self.player.equipped.get(s)} (장착됨)" if self.player.equipped.get(s) else "(없음)"
                    combobox.set(cb_cur)
                    self.equip_mappings[s] = new_mapping
                    self.update_info()
                    # 인벤토리 창이 열려 있으면 즉시 갱신
                    self.refresh_inventory_display()
                return on_selected

            cb.bind("<<ComboboxSelected>>", make_cb_handler(slot, cb))
            self.equip_widgets[slot] = cb
            self.equip_mappings[slot] = mapping



    def attempt_enhance(self, slot):
        # === 장비 강화 로직 ===
        # 1. 장착 아이템 확인
        # 2. 비용 계산 및 골드 차감
        # 3. 성공 확률 계산 (config 참조)
        # 4. 결과 처리 (성공/실패/파괴)
        
        p = self.player
        if not p:
            return
        item = p.equipped.get(slot)
        if not item:
            self.log("❌ 해당 슬롯에 장착된 아이템이 없습니다.", "red")
            return
        cur = p.enhancements.get(item, 0)
        if cur >= 20:
            self.log(f"✅ {item}은(는) 이미 +{cur} (최대)", "green")
            return

        # 마을에서만 강화 가능 (UI/게임 규칙)
        if hasattr(self, 'title_label') and self.title_label.cget('text') != '마을':
            self.log("❌ 강화는 마을에서만 가능합니다.", "red")
            return

        # 시도 비용 계산 (현재 레벨 기반)
        cost = enhance_cost_for_level(cur)
        if p.gold < cost:
            self.log(f"💰 골드가 부족합니다. 필요 골드: {cost}G", "red")
            return
        # 비용 선차감: 시도는 비용을 소비함
        p.gold -= cost

        # 성공 확률 산출
        chance = enhance_success_chance(cur)
        roll = random.random()
        success = roll < chance

        if success:
            # 성공 시 레벨 증가
            p.enhancements[item] = cur + 1
            newlvl = cur + 1
            self.log(f"🎉 강화 성공: {item} +{newlvl} (확률 {int(chance*100)}%) — 소모 {cost}G", "level_up")
        else:
            # 실패 시 페널티 적용: config의 규칙을 따름
            applied = False
            for rng, info in ENHANCE_PENALTIES.items():
                if '-' in rng:
                    lo, hi = [int(x) for x in rng.split('-',1)]
                    if lo <= cur <= hi:
                        # 파괴 타입인지 하락 타입인지 판별
                        if info.get('type') == 'destroy':
                            # 장착 중이면 장비 파괴 처리: 장비 해제 및 제거
                            self.log(f"💥 강화 실패: {item} 파괴되었습니다! (확률 {int(chance*100)}%)", "red")
                            # 장비에서 제거
                            for s, name in list(p.equipped.items()):
                                if name == item:
                                    p.equipped[s] = None
                            # 인벤토리에서도 제거(있다면)
                            p.inv = [i for i in p.inv if i != item]
                            if item in p.enhancements:
                                del p.enhancements[item]
                        else:
                            max_drop = info.get('max_drop', 0)
                            drop = random.randint(1, max_drop) if max_drop > 0 else 1
                            newlvl = max(0, cur - drop)
                            p.enhancements[item] = newlvl
                            self.log(f"⚠️ 강화 실패: {item} -{drop} 단계 (새 레벨: +{newlvl}) — 소모 {cost}G", "red")
                        applied = True
                        break
            if not applied:
                # 기본 페널티(보수적): 1단계 하락
                newlvl = max(0, cur - 1)
                p.enhancements[item] = newlvl
                self.log(f"⚠️ 강화 실패: {item} -1 단계 (새 레벨: +{newlvl}) — 소모 {cost}G", "red")

        # UI 및 인벤토리 갱신
        self.refresh_equipment_options()
        self.refresh_inventory_display()
        self.update_info()


    def refresh_inventory_display(self):
        # 인벤토리 창에 변화가 있으면 즉시 반영합니다
        if hasattr(self, '_inv_refresh_fn') and callable(self._inv_refresh_fn):
            try:
                self._inv_refresh_fn()
            except Exception:
                pass
        elif self.inv_window and tk.Toplevel.winfo_exists(self.inv_window):
            # 안전하게 찾아서 갱신
            for widget in self.inv_window.winfo_children():
                if isinstance(widget, tk.Listbox):
                    lb = widget
                    lb.delete(0, tk.END)
                    for item in self.player.inv:
                        lb.insert(tk.END, item)
        # 장비 창이 열려 있으면 옵션 목록도 갱신
        self.refresh_equipment_options()

    def refresh_equipment_options(self):
        if not self.equip_window or not tk.Toplevel.winfo_exists(self.equip_window):
            return
        slots = ["투구", "갑옷", "장갑", "신발", "무기", "방패"]
        for s in slots:
            cb = self.equip_widgets.get(s)
            if not cb:
                continue
            current = self.player.equipped.get(s)
            inv_names = []
            for name in list(self.player.inv):
                entry = next((e for e in SHOP_ITEMS if e.get('이름') == name), None)
                if entry and entry.get('부위') == s:
                    inv_names.append(name)
            if current and current not in inv_names:
                inv_names.append(current)
            new_display = ['(없음)']
            new_mapping = {'(없음)': None}
            for n in inv_names:
                d = f"{n} (장착됨)" if current == n else n
                new_display.append(d)
                new_mapping[d] = n
                new_mapping[n] = n
            cb.config(values=new_display)
            cur = f"{current} (장착됨)" if current else "(없음)"
            cb.set(cur)
            self.equip_mappings[s] = new_mapping

    def buy_item(self, item, price, qty=1):
        p = self.player
        total_cost = price * qty
        if p.gold >= total_cost:
            p.gold -= total_cost
            for _ in range(qty):
                p.inv.append(item)
            # 구매 메시지는 볼드 처리
            self.log(f"🛒 {item} x{qty} 구매 완료" if qty > 1 else f"🛒 {item} 구매 완료", "bold_item")
            self.update_info()
            self.refresh_inventory_display()
            
            # 장착 팝업 (장비 아이템이고 1개 구매 시)
            entry = next((e for e in SHOP_ITEMS if e.get('이름') == item), None)
            if entry and entry.get('부위') and qty == 1:
                parent = self.shop_window if (self.shop_window and tk.Toplevel.winfo_exists(self.shop_window)) else self.root
                if messagebox.askyesno("장착 확인", f"{item}을(를) 바로 장착하시겠습니까?", parent=parent):
                    slot = entry.get('부위')
                    prev = p.equipped.get(slot)
                    if prev:
                        if prev not in p.inv:
                            p.inv.append(prev)
                    p.equipped[slot] = item
                    if item in p.inv:
                        p.inv.remove(item)
                    self.log(f"⚔️ {item} 장착 ({slot})", "bold_item")
                    self.update_info()
                    self.refresh_equipment_options()
                    self.refresh_inventory_display()
        else:
            self.log("💰 골드가 부족합니다.", "red")

# ===== 실행 =====
if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()   # 기본 Tk 창 숨기기
    app = RPGApp(root)
    root.mainloop()    