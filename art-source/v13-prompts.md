# v1.3 生成素材记录

工具：内置 imagegen。背景：透明。参考：用户提供的大蒜猫抓板照片，以及项目已有的 `assets/walk-0.png` 猫咪形象。原始聊天照片不随仓库发布。脚本只做透明区域整理、切帧、等比缩放、基线与端点配准、64 FPS 编码；交互球由程序独立绘制和模拟。

## garlic-scratcher.png

Create a single isolated photorealistic game prop sprite on a genuinely transparent background, based on this reference garlic cat scratching toy. Full object entirely visible, front view with a slight view down onto the base, soft natural lighting matching a photo-style desktop cat. Preserve its recognizable shape: three plush green upright leaves; a fat rounded garlic bulb wrapped in many horizontal rings of white sisal rope, two funny round eyes and a red smiling mouth; a natural wooden round base with a clearly visible recessed circular annular track around the bulb. IMPORTANT: the annular track is EMPTY, no balls anywhere, no dangling string or dangling ball, because the game will draw independently moving balls. Leave the entire front half of the track unobstructed and easy to see. No cat, no room, no floor, no text, no logo, no watermark, no packaging. Center object with transparent margins. Detailed rope texture, clean silhouette, high quality product cutout.

运行素材：`assets/props/garlic-scratcher.png`。

## scratch-turn.png

Create a photo-style animation sprite sheet of THIS EXACT golden British shorthair cat, preserve its round cheeks, green eyes, cream muzzle/chest, golden short fur, stocky build. Transparent background, no scenery, no props, no shadows detached from cat, no text, no grid lines. Exactly 8 separate full-body cats in a perfectly regular 4 columns by 2 rows grid, one cat centered in each equal cell with broad transparent gaps, no overlap or clipping. Same scale, camera, lighting and identity in all cells. TOP ROW four consecutive scratching poses: cat facing RIGHT, rear paws planted on the floor, torso raised/leaning forward, alternating front paws reaching outward/upward against an invisible vertical scratching surface at the RIGHT edge. Pose1 paws resting forward, pose2 right paw lifted higher, pose3 right paw pulled down while left paw lifts, pose4 left paw pulled down toward resting. Make front paws clearly extend toward the right; do not include the scratcher itself. BOTTOM ROW four consecutive standing turn poses with ALL FOUR PAWS ON THE FLOOR, never sitting: side-on facing right, three-quarter facing camera/right, three-quarter facing camera/left, side-on facing left. Keep standing body and paws grounded at exactly same baseline and same center. Smooth plausible small differences suitable for interpolation. The source image is the identity and photo-style reference, not a separate cell to paste.

运行素材：`scratch-*.png`、`bridge_stand_turn-*.png` 及对应 WebP。转身端点使用既有站姿和其镜像，保持接缝一致。

## prop-interactions.png

Photo-style game animation sprite sheet, exactly 4 columns and 2 rows of this SAME golden British shorthair cat, round head green eyes cream muzzle golden fur same camera and identity throughout. One entire cat per cell, broad empty transparent margins, genuinely transparent background. NO props, NO balls, NO bowls, NO food, NO shadow, no labels, no text, no scenery. TOP ROW four consecutive sitting low paw batting poses facing RIGHT: hindquarters seated, left front paw supports the body, right front paw reaches toward an invisible small ball on the floor at far right, paw lifts slightly, then bats forward low near the ground, then returns. Cat's body stays stable, only paw and head follow ball. All toes complete and anatomically plausible. BOTTOM ROW four consecutive feeding poses facing RIGHT: standing/low crouching on four legs, head lowers toward imaginary food on the floor near the right front paw; mouth makes tiny eating movements; head slightly lifts. There is NO BOWL in any cell. Same scale and baseline in all frames within each row, fully isolated cat only, realistic fur consistent with reference. Clean transparent silhouette, absolutely no checkerboard pattern baked in.

运行素材：`ball-*.png`、`sniff-*.png`、`eat-*.png`、`drink-*.png` 及对应 WebP。
