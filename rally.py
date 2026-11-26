"""Two-way play using the independent desktop ball and existing cat poses."""

from dataclasses import dataclass
import math

from cat_model import clamp


BALL_CLIP_SECONDS = 1.328
PLAY_WINDOW_WIDTH = 320
CAT_FLOOR = 286
PAW_Y = 270


@dataclass
class BallRally:
    grabbed: bool = False
    facing: int = 1
    retreat_to: tuple[float, float] | None = None
    return_origin: float = 0.0

    def reset(self):
        self.grabbed = False
        self.facing = 1
        self.retreat_to = None
        self.return_origin = 0.0

    @staticmethod
    def _paw_offset(direction):
        return 270 if direction == 1 else 50

    def _stand_position(self, scene, x, y, scale):
        ball = scene.ball
        left, _, right, _ = scene.limits
        floor_y = ball.floor - CAT_FLOOR * scale
        candidates = []
        for direction in (self.facing, -self.facing):
            target_x = ball.x - self._paw_offset(direction) * scale
            target = scene._reachable(target_x, floor_y)
            if target is None:
                continue
            runway = right + 270 * scale - ball.x if direction == 1 else ball.x - left - 50 * scale
            # A serve gets a clear roll instead of immediately hitting the desktop edge.
            score = (runway < 70 * scale, math.dist((x, y), target) +
                     (0 if direction == self.facing else 12 * scale))
            candidates.append((score, target, direction))
        if not candidates:
            return None
        _, target, direction = min(candidates, key=lambda item: item[0])
        return target, direction

    def _walk_to(self, scene, model, target, *, hurry=False):
        scene.destination = target
        if model.action not in {'walk', 'trot'}:
            model.queue.clear()
            model.start('trot' if hurry else 'walk')
        model.remaining = max(model.remaining, 1.0)

    def _hold(self, model):
        if model.action != 'look':
            model.queue.clear()
            model.start('look')
        model.remaining = max(model.remaining, 1.0)

    def _roll(self, scene, direction, speed, scale):
        """Limit the travel so ordinary serves finish within a paw's reach."""
        ball = scene.ball
        left, _, right, _ = scene.limits
        inner = (left + 52 * scale, right + (PLAY_WINDOW_WIDTH - 52) * scale)
        runway = inner[1] - ball.x if direction == 1 else ball.x - inner[0]
        if runway < 8 * scale:
            return False
        # Ball.step uses exponential drag (1.25/s). Leave a little room for
        # the integration step and for rolling balls on narrow displays.
        ball.velocity = direction * min(speed, 1.23 * runway)
        return True

    def push(self, scene, model, x, y, scale, velocity=None):
        """Release a ball during the player's turn. A click aims toward the cat."""
        activity = scene.activity
        if not activity or activity.kind != 'rally' or activity.stage not in {'retreat', 'wait'}:
            return False
        ball = scene.ball
        if ball is None:
            return False
        toward_cat = x + 160 * scale - ball.x
        aimed_direction = 1 if toward_cat >= 0 else -1
        if velocity is None or not math.isfinite(velocity) or abs(velocity) < 35 * scale:
            direction = aimed_direction
            speed = clamp(abs(toward_cat) * 1.25 + 45 * scale, 110 * scale, 320 * scale)
        else:
            direction = 1 if velocity > 0 else -1
            speed = clamp(abs(velocity), 100 * scale, 320 * scale)
        if not self._roll(scene, direction, speed, scale):
            if not self._roll(scene, aimed_direction, 155 * scale, scale):
                return False
        self.grabbed = False
        self.return_origin = ball.x
        scene._enter('incoming', model, 'look')
        scene.message = '悠米盯住了滚过来的球'
        return True

    def update(self, scene, model, x, y, scale, ready, phase):
        activity = scene.activity
        ball = scene.ball
        if ball is None:
            scene.cancel(model)
            return
        if self.grabbed:
            self._hold(model)
            return

        scene.direction = self.facing
        stage = activity.stage
        if stage == 'retreat':
            if self.retreat_to is not None and math.dist((x, y), self.retreat_to) > 4 * scale:
                if activity.stage_time < 2.5:
                    self._walk_to(scene, model, self.retreat_to)
                    return
            scene._enter('wait', model, 'look')
            return
        if stage == 'wait':
            self._hold(model)
            if activity.stage_time > 25:
                scene.cancel(model)
                scene.message = '小球留在这儿，下次再一起玩'
            return
        if stage == 'incoming':
            self._hold(model)
            if abs(ball.x - self.return_origin) >= 6 * scale:
                distance = math.dist((x + 160 * scale, y + CAT_FLOOR * scale), (ball.x, ball.floor))
                scene._enter('approach', model, 'trot' if distance > 240 * scale else 'walk')
                scene.message = '悠米去接球啦'
            elif activity.stage_time > 0.9:
                scene._enter('wait', model, 'look')
                scene.message = '再轻轻拨一下小球试试'
            return

        if stage == 'serve' and model.action == 'ball':
            self._serve(scene, model, x, y, scale, ready, phase)
            return

        placement = self._stand_position(scene, x, y, scale)
        if placement is None:
            if abs(ball.velocity) >= 10 * scale:
                self._hold(model)
                return
            scene._enter('wait', model, 'look')
            scene.message = '球有点远，点一下把它拨回悠米身边'
            return
        target, direction = placement
        self.facing = scene.direction = direction
        distance = math.dist((x, y), target)
        if distance >= 5 * scale or abs(ball.velocity) > 34 * scale:
            self._walk_to(scene, model, target, hurry=distance > 230 * scale)
            return
        scene._enter('serve', model, 'ball')

    def _serve(self, scene, model, x, y, scale, ready, phase):
        activity = scene.activity
        ball = scene.ball
        paw_x = x + self._paw_offset(self.facing) * scale
        paw_y = y + PAW_Y * scale
        # The ball's centre is one radius above the ground, not on the baseline.
        distance = math.dist((paw_x, paw_y), (ball.x, ball.floor - ball.radius))
        if distance > 18 * scale:
            scene._enter('approach', model, 'walk')
            return
        model.remaining = max(model.remaining, 1.0)
        if not ready or not 0.48 <= (phase / BALL_CLIP_SECONDS) % 1.0 <= 0.75:
            return
        if not self._roll(scene, self.facing, 155 * scale, scale):
            scene._enter('wait', model, 'look')
            scene.message = '球已靠边，点一下把它拨回来'
            return
        activity.strikes += 1
        model.happiness = clamp(model.happiness + 0.8)
        model.energy = clamp(model.energy - 0.4)
        self.retreat_to = scene._target(x - self.facing * 24 * scale, y)
        scene._enter('retreat', model, 'look')
        scene.message = '轮到你啦！点击小球，或把球横着一拨'
