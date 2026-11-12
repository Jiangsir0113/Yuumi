"""Local, deterministic behavior model for Jintuan. No UI or network dependencies."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
import os
from pathlib import Path
import random


@dataclass(frozen=True)
class Action:
    label: str
    sprite: str
    seconds: float
    keyframe_fps: float = 3.0  # Authoring rate; encoded/runtime motion is 64 fps.


ACTIONS = {
    "idle": Action("陪你发呆", "idle", 10, 2.2),
    "look": Action("看看你", "look", 4, 2),
    "walk": Action("慢慢逛", "walk", 8, 6),
    "trot": Action("小跑一下", "walk", 4, 10),
    "loaf": Action("揣手手", "loaf", 22, 1),
    "sleep": Action("睡个好觉", "sleep", 120, .65),
    "yawn": Action("困困了", "yawn", 3, 1.5),
    "stretch": Action("伸个懒腰", "stretch", 4, 1.5),
    "head": Action("摸摸头，呼噜…", "head", 4, 2),
    "chin": Action("这里好舒服", "chin", 4, 2),
    "back": Action("顺顺毛", "back", 4, 2),
    "cheek": Action("揉揉小圆脸", "nuzzle", 4, 2),
    "paw": Action("轻轻碰爪爪", "paw", 4, 2),
    "refuse": Action("先歇一会儿嘛", "refuse", 2, 2),
    "nuzzle": Action("蹭蹭你", "nuzzle", 5, 2),
    "knead": Action("踩奶进行中", "knead", 7, 3),
    "wave": Action("喵，看看我", "wave", 4, 2),
    "sniff": Action("闻一闻", "sniff", 2, 2),
    "eat": Action("咔嚓咔嚓", "eat", 7, 3),
    "treat": Action("小零食时间", "eat", 4, 3),
    "drink": Action("吨吨吨", "drink", 6, 3),
    "lick": Action("舔舔嘴", "lick", 2, 2),
    "groom": Action("洗脸理毛", "groom", 5, 3),
    "crouch": Action("瞄准了…", "crouch", 3, 3),
    "pounce": Action("扑到啦", "pounce", .9, 5),
    "ball": Action("拍小球", "ball", 7, 3),
}
TOUCH_ACTIONS = {"head", "chin", "back", "cheek", "paw"}
CARE_ACTIONS = {"sniff", "eat", "treat", "drink", "lick", "groom"}
DEFAULT_SETTINGS = {"size": 1.0, "roam": True, "sound": False,
                    "hide_fullscreen": True, "screen": 0, "name": "悠米"}


def clamp(value: float, low=0., high=100.) -> float:
    return max(low, min(high, value))


@dataclass
class CatModel:
    satiety: float = 75.
    thirst: float = 80.
    energy: float = 80.
    happiness: float = 75.
    affinity: float = 55.
    touch_load: float = 0.
    cooldown: float = 0.
    action: str = "idle"
    elapsed: float = 0.
    remaining: float = 10.
    queue: list[str] = field(default_factory=list)
    settings: dict = field(default_factory=lambda: DEFAULT_SETTINGS.copy())
    rng: random.Random = field(default_factory=random.Random, repr=False)
    last_message: str = ""

    @property
    def sleeping(self):
        return self.action == "sleep"

    def start(self, action: str, seconds: float | None = None):
        if action not in ACTIONS:
            raise ValueError(f"Unknown action: {action}")
        self.action = action
        self.elapsed = 0.
        self.remaining = ACTIONS[action].seconds if seconds is None else seconds

    def sequence(self, actions: list[str]):
        if not actions or any(x not in ACTIONS for x in actions):
            raise ValueError("Invalid action sequence")
        self.queue = list(actions[1:])
        self.start(actions[0])

    def request(self, action: str):
        """An intentional user action overrides autonomous behavior."""
        if action in TOUCH_ACTIONS:
            return self.touch(action, .6)
        if action == "food":
            if self.action in {"sniff", "eat", "treat", "drink"}:
                self.last_message = "慢慢吃，不着急～"
                return False
            if self.satiety > 96:
                self.last_message = "已经吃饱啦，陪我玩会儿？"
                self.queue.clear()
                self.start("lick")
                return False
            self.sequence(["sniff", "eat", "lick", "groom"])
        elif action == "water":
            if self.action in {"sniff", "eat", "treat", "drink"}:
                self.last_message = "等我喝完这一口～"
                return False
            self.sequence(["sniff", "drink", "lick"])
        elif action == "snack":
            if self.action in {"sniff", "eat", "treat", "drink"}:
                return False
            if self.satiety > 96:
                self.last_message = "小肚子装不下啦～"
                return False
            self.sequence(["sniff", "treat", "lick"])
        elif action == "sleep":
            self.queue.clear()
            self.start("sleep")
        elif action == "wake":
            self.queue.clear()
            self.start("idle")
        elif action == "toy":
            self.sequence(["crouch", "pounce", "ball", "groom"])
        elif action == "ball":
            self.sequence(["crouch", "ball", "groom"])
        else:
            self.queue.clear()
            self.start(action)
        return True

    def touch(self, region: str, seconds: float = .2):
        if region not in TOUCH_ACTIONS:
            raise ValueError("Invalid touch region")
        seconds = clamp(seconds, .05, .7)
        if self.cooldown > 0:
            self.last_message = "给我一点点自己的时间～"
            if self.action != "refuse":
                self.queue.clear()
                self.start("refuse")
            return False
        sensitivity = 1.5 if region == "paw" else 1.
        self.touch_load = clamp(self.touch_load + seconds * 9 * sensitivity)
        if self.touch_load >= 82:
            self.cooldown = 18.
            self.queue.clear()
            self.start("refuse")
            self.last_message = "有点痒啦，先让我歇歇～"
            return False
        self.happiness = clamp(self.happiness + seconds * 1.5)
        self.affinity = clamp(self.affinity + seconds * .14)
        self.queue.clear()
        if self.action != region:
            self.start(region)
        self.remaining = 3.5
        return True

    def autonomous(self):
        if self.energy < 22:
            self.sequence(["yawn", "loaf", "sleep"])
            return
        if self.cooldown > 0:
            self.start("walk" if self.settings["roam"] else "loaf", 7)
            return
        choices = ["idle", "idle", "loaf", "look", "groom", "stretch"]
        if self.settings["roam"]:
            choices += ["walk", "walk", "trot"]
        if self.affinity > 45:
            choices += ["wave", "nuzzle", "knead"]
        if self.satiety < 30:
            choices += ["wave"]
        self.start(self.rng.choice(choices))

    def complete(self):
        # Nutrition accrues only over actual consumed time in tick().
        if self.action == "eat":
            self.happiness = clamp(self.happiness + 5)
        elif self.action == "treat":
            self.happiness = clamp(self.happiness + 8)
        elif self.action in {"ball", "pounce"}:
            self.happiness = clamp(self.happiness + 6)
            self.energy = clamp(self.energy - 2)
        if self.queue:
            next_action = self.queue.pop(0)
            self.start(next_action, 5 if next_action == "loaf" and "sleep" in self.queue else None)
        else:
            self.autonomous()

    def tick(self, dt: float, touching: bool = False):
        if not math.isfinite(dt) or dt < 0:
            raise ValueError("Time delta must be finite and nonnegative")
        # Split large timer gaps into transitions without losing completed care.
        dt = min(dt, 300.)
        self.satiety = clamp(self.satiety - dt * .022)
        self.thirst = clamp(self.thirst - dt * .018)
        self.happiness = clamp(self.happiness - dt * .003)
        self.energy = clamp(self.energy + dt * (.23 if self.sleeping else -.008))
        self.cooldown = max(0., self.cooldown - dt)
        if not touching:
            self.touch_load = max(0., self.touch_load - dt * 1.8)
        budget = dt
        for _ in range(150):
            if touching and self.action in TOUCH_ACTIONS and self.cooldown<=0:
                self.remaining=max(self.remaining,budget+.2)
            amount = min(budget, self.remaining)
            if self.action=="eat":
                self.satiety=clamp(self.satiety+amount*5)
            elif self.action=="treat":
                self.satiety=clamp(self.satiety+amount*3)
            elif self.action=="drink":
                self.thirst=clamp(self.thirst+amount*7.5)
            self.remaining -= amount
            self.elapsed += amount
            budget -= amount
            if self.remaining <= .00001:
                self.complete()
            if budget <= .00001:
                break

    def status(self):
        if self.cooldown > 0:
            return "想自己待一小会儿"
        if self.sleeping:
            return "睡得很安心"
        if self.satiety < 30:
            return "有点想吃猫粮了"
        if self.thirst < 30:
            return "想喝点水"
        if self.energy < 30:
            return "困困的，想休息"
        if self.happiness > 80:
            return "今天也很喜欢你"
        return "在你身边就很安心"

    def serialize(self):
        return {"version": 1, "needs": {k: getattr(self, k) for k in
                ("satiety", "thirst", "energy", "happiness", "affinity")},
                "settings": self.settings}

    @classmethod
    def load(cls, path: Path):
        model = cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            for k in ("satiety", "thirst", "energy", "happiness", "affinity"):
                val = data.get("needs", {}).get(k)
                if isinstance(val, (int, float)) and math.isfinite(val):
                    setattr(model, k, clamp(val))
            settings = data.get("settings", {})
            if isinstance(settings, dict):
                for k in ("roam", "sound", "hide_fullscreen"):
                    if type(settings.get(k)) is bool:
                        model.settings[k] = settings[k]
                size = settings.get("size")
                if isinstance(size, (float, int)) and math.isfinite(size):
                    model.settings["size"] = clamp(size, .65, 1.5)
                screen = settings.get("screen")
                if type(screen) is int and screen >= 0:
                    model.settings["screen"] = screen
                name = settings.get("name")
                if isinstance(name, str) and name.strip():
                    model.settings["name"] = "悠米" if name.strip() in {"金团", "金团桌宠"} else name.strip()[:12]
                pos = settings.get("position")
                if isinstance(pos, list) and len(pos) == 2 and all(type(x) is int for x in pos):
                    model.settings["position"] = pos
        except (OSError, ValueError, TypeError, AttributeError):
            pass  # A missing/corrupt save never prevents the cat from opening.
        return model

    def save(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(self.serialize(), ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, path)
