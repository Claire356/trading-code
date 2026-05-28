const canvas = document.querySelector("#game");
const ctx = canvas.getContext("2d");

const scoreEl = document.querySelector("#score");
const waveEl = document.querySelector("#wave");
const livesEl = document.querySelector("#lives");
const overlay = document.querySelector("#overlay");
const messageEl = document.querySelector("#message");
const startButton = document.querySelector("#startButton");

const keys = new Set();
const touch = {
  left: false,
  right: false,
  fire: false
};

const state = {
  running: false,
  gameOver: false,
  score: 0,
  wave: 1,
  lives: 3,
  time: 0,
  lastShot: 0,
  nextEnemy: 0,
  nextRock: 0,
  shake: 0,
  player: null,
  shots: [],
  enemies: [],
  rocks: [],
  sparks: [],
  stars: []
};

const DPR_LIMIT = 2;
const WORLD = {
  width: 960,
  height: 540
};

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function random(min, max) {
  return min + Math.random() * (max - min);
}

function distance(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function resizeCanvas() {
  const rect = canvas.getBoundingClientRect();
  const dpr = Math.min(window.devicePixelRatio || 1, DPR_LIMIT);
  canvas.width = Math.max(1, Math.floor(rect.width * dpr));
  canvas.height = Math.max(1, Math.floor(rect.height * dpr));
  ctx.setTransform(canvas.width / WORLD.width, 0, 0, canvas.height / WORLD.height, 0, 0);
}

function makePlayer() {
  return {
    x: WORLD.width / 2,
    y: WORLD.height - 78,
    radius: 18,
    speed: 420,
    invincible: 1.2
  };
}

function seedStars() {
  state.stars = Array.from({ length: 125 }, () => ({
    x: random(0, WORLD.width),
    y: random(0, WORLD.height),
    radius: random(0.6, 1.9),
    speed: random(26, 98),
    tint: Math.random() > 0.78 ? "#f8c55a" : "#eef4ff"
  }));
}

function resetGame() {
  state.running = true;
  state.gameOver = false;
  state.score = 0;
  state.wave = 1;
  state.lives = 3;
  state.time = 0;
  state.lastShot = 0;
  state.nextEnemy = 0.7;
  state.nextRock = 1.1;
  state.shake = 0;
  state.player = makePlayer();
  state.shots = [];
  state.enemies = [];
  state.rocks = [];
  state.sparks = [];
  updateHud();
  overlay.classList.add("is-hidden");
}

function updateHud() {
  scoreEl.textContent = state.score.toString();
  waveEl.textContent = state.wave.toString();
  livesEl.textContent = state.lives.toString();
}

function fireShot() {
  if (!state.running || state.time - state.lastShot < 0.18) {
    return;
  }

  state.lastShot = state.time;
  state.shots.push({
    x: state.player.x,
    y: state.player.y - 24,
    vx: 0,
    vy: -620,
    radius: 4,
    life: 1.2
  });
}

function spawnEnemy() {
  const speed = random(82, 130) + state.wave * 12;
  state.enemies.push({
    x: random(36, WORLD.width - 36),
    y: -34,
    vx: random(-38, 38),
    vy: speed,
    radius: random(16, 22),
    phase: random(0, Math.PI * 2),
    hp: 1
  });
}

function spawnRock() {
  const size = random(15, 33);
  state.rocks.push({
    x: random(30, WORLD.width - 30),
    y: -40,
    vx: random(-52, 52),
    vy: random(88, 150) + state.wave * 10,
    radius: size,
    spin: random(-3, 3),
    angle: random(0, Math.PI * 2)
  });
}

function addBurst(x, y, color, amount = 12) {
  for (let i = 0; i < amount; i += 1) {
    const angle = random(0, Math.PI * 2);
    const speed = random(70, 260);
    state.sparks.push({
      x,
      y,
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed,
      radius: random(1.2, 3.2),
      color,
      life: random(0.28, 0.62)
    });
  }
}

function hitPlayer() {
  if (state.player.invincible > 0) {
    return;
  }

  state.lives -= 1;
  state.player.invincible = 1.4;
  state.shake = 0.28;
  addBurst(state.player.x, state.player.y, "#f06658", 24);
  updateHud();

  if (state.lives <= 0) {
    endGame();
  }
}

function endGame() {
  state.running = false;
  state.gameOver = true;
  messageEl.textContent = `Final score: ${state.score}`;
  startButton.textContent = "Restart";
  overlay.classList.remove("is-hidden");
}

function updateStars(dt) {
  for (const star of state.stars) {
    star.y += star.speed * dt * (state.running ? 1.25 : 0.45);
    if (star.y > WORLD.height + 6) {
      star.x = random(0, WORLD.width);
      star.y = -6;
      star.speed = random(26, 98);
    }
  }
}

function updatePlayer(dt) {
  const left = keys.has("ArrowLeft") || keys.has("KeyA") || touch.left;
  const right = keys.has("ArrowRight") || keys.has("KeyD") || touch.right;
  const fire = keys.has("Space") || keys.has("ArrowUp") || keys.has("KeyW") || touch.fire;
  const direction = (right ? 1 : 0) - (left ? 1 : 0);

  state.player.x = clamp(state.player.x + direction * state.player.speed * dt, 30, WORLD.width - 30);
  state.player.invincible = Math.max(0, state.player.invincible - dt);

  if (fire) {
    fireShot();
  }
}

function updateActors(dt) {
  state.nextEnemy -= dt;
  state.nextRock -= dt;

  if (state.nextEnemy <= 0) {
    spawnEnemy();
    state.nextEnemy = clamp(1.1 - state.wave * 0.05, 0.36, 1.1);
  }

  if (state.nextRock <= 0) {
    spawnRock();
    state.nextRock = clamp(1.55 - state.wave * 0.06, 0.48, 1.55);
  }

  for (const shot of state.shots) {
    shot.x += shot.vx * dt;
    shot.y += shot.vy * dt;
    shot.life -= dt;
  }

  for (const enemy of state.enemies) {
    enemy.phase += dt * 3;
    enemy.x += (enemy.vx + Math.sin(enemy.phase) * 42) * dt;
    enemy.y += enemy.vy * dt;
  }

  for (const rock of state.rocks) {
    rock.x += rock.vx * dt;
    rock.y += rock.vy * dt;
    rock.angle += rock.spin * dt;
  }

  for (const spark of state.sparks) {
    spark.x += spark.vx * dt;
    spark.y += spark.vy * dt;
    spark.vx *= 0.985;
    spark.vy *= 0.985;
    spark.life -= dt;
  }

  state.shots = state.shots.filter((shot) => shot.life > 0 && shot.y > -24);
  state.enemies = state.enemies.filter((enemy) => enemy.y < WORLD.height + 48);
  state.rocks = state.rocks.filter((rock) => rock.y < WORLD.height + 56);
  state.sparks = state.sparks.filter((spark) => spark.life > 0);
}

function handleCollisions() {
  for (const shot of state.shots) {
    if (shot.hit) {
      continue;
    }

    for (const enemy of state.enemies) {
      if (!enemy.hit && distance(shot, enemy) < shot.radius + enemy.radius) {
        shot.hit = true;
        enemy.hit = true;
        state.score += 100;
        addBurst(enemy.x, enemy.y, "#54d6c7", 15);
        break;
      }
    }

    if (shot.hit) {
      continue;
    }

    for (const rock of state.rocks) {
      if (!rock.hit && distance(shot, rock) < shot.radius + rock.radius) {
        shot.hit = true;
        rock.hit = true;
        state.score += 45;
        addBurst(rock.x, rock.y, "#f8c55a", 12);
        break;
      }
    }
  }

  state.shots = state.shots.filter((shot) => !shot.hit);
  state.enemies = state.enemies.filter((enemy) => !enemy.hit);
  state.rocks = state.rocks.filter((rock) => !rock.hit);

  for (const enemy of state.enemies) {
    if (distance(state.player, enemy) < state.player.radius + enemy.radius * 0.78) {
      enemy.hit = true;
      hitPlayer();
    }
  }

  for (const rock of state.rocks) {
    if (distance(state.player, rock) < state.player.radius + rock.radius * 0.78) {
      rock.hit = true;
      hitPlayer();
    }
  }

  state.enemies = state.enemies.filter((enemy) => !enemy.hit);
  state.rocks = state.rocks.filter((rock) => !rock.hit);
  state.wave = 1 + Math.floor(state.score / 900);
  updateHud();
}

function update(dt) {
  state.time += dt;
  state.shake = Math.max(0, state.shake - dt);
  updateStars(dt);

  if (!state.running) {
    return;
  }

  updatePlayer(dt);
  updateActors(dt);
  handleCollisions();
}

function drawBackground() {
  const gradient = ctx.createLinearGradient(0, 0, 0, WORLD.height);
  gradient.addColorStop(0, "#070912");
  gradient.addColorStop(0.55, "#0a1020");
  gradient.addColorStop(1, "#10110f");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, WORLD.width, WORLD.height);

  ctx.save();
  ctx.globalAlpha = 0.13;
  ctx.fillStyle = "#54d6c7";
  ctx.beginPath();
  ctx.arc(96, 92, 170, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "#f06658";
  ctx.beginPath();
  ctx.arc(WORLD.width - 112, WORLD.height - 42, 130, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();

  for (const star of state.stars) {
    ctx.globalAlpha = clamp(star.radius / 1.8, 0.35, 1);
    ctx.fillStyle = star.tint;
    ctx.beginPath();
    ctx.arc(star.x, star.y, star.radius, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.globalAlpha = 1;
}

function drawPlayer() {
  const p = state.player;
  const flicker = p.invincible > 0 && Math.floor(state.time * 14) % 2 === 0;
  if (flicker) {
    ctx.globalAlpha = 0.45;
  }

  ctx.save();
  ctx.translate(p.x, p.y);

  ctx.fillStyle = "#eef4ff";
  ctx.beginPath();
  ctx.moveTo(0, -25);
  ctx.lineTo(22, 22);
  ctx.lineTo(7, 14);
  ctx.lineTo(0, 25);
  ctx.lineTo(-7, 14);
  ctx.lineTo(-22, 22);
  ctx.closePath();
  ctx.fill();

  ctx.fillStyle = "#54d6c7";
  ctx.beginPath();
  ctx.moveTo(0, -11);
  ctx.lineTo(8, 11);
  ctx.lineTo(-8, 11);
  ctx.closePath();
  ctx.fill();

  ctx.globalAlpha = 0.86;
  ctx.fillStyle = "#f8c55a";
  ctx.beginPath();
  ctx.moveTo(-7, 23);
  ctx.lineTo(0, 36 + Math.sin(state.time * 30) * 5);
  ctx.lineTo(7, 23);
  ctx.closePath();
  ctx.fill();

  ctx.restore();
  ctx.globalAlpha = 1;
}

function drawShots() {
  ctx.fillStyle = "#54d6c7";
  ctx.shadowBlur = 16;
  ctx.shadowColor = "#54d6c7";
  for (const shot of state.shots) {
    ctx.fillRect(shot.x - 3, shot.y - 16, 6, 22);
  }
  ctx.shadowBlur = 0;
}

function drawEnemy(enemy) {
  ctx.save();
  ctx.translate(enemy.x, enemy.y);
  ctx.fillStyle = "#f06658";
  ctx.beginPath();
  ctx.moveTo(0, 21);
  ctx.lineTo(22, -14);
  ctx.lineTo(8, -7);
  ctx.lineTo(0, -24);
  ctx.lineTo(-8, -7);
  ctx.lineTo(-22, -14);
  ctx.closePath();
  ctx.fill();

  ctx.fillStyle = "#231116";
  ctx.beginPath();
  ctx.arc(0, -2, 6, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

function drawRock(rock) {
  ctx.save();
  ctx.translate(rock.x, rock.y);
  ctx.rotate(rock.angle);
  ctx.fillStyle = "#8b887d";
  ctx.strokeStyle = "#d6c9a4";
  ctx.lineWidth = 2;
  ctx.beginPath();
  const points = 9;
  for (let i = 0; i < points; i += 1) {
    const angle = (Math.PI * 2 * i) / points;
    const radius = rock.radius * randomShape(i);
    const x = Math.cos(angle) * radius;
    const y = Math.sin(angle) * radius;
    if (i === 0) {
      ctx.moveTo(x, y);
    } else {
      ctx.lineTo(x, y);
    }
  }
  ctx.closePath();
  ctx.fill();
  ctx.stroke();
  ctx.restore();
}

function randomShape(index) {
  const values = [0.85, 1.05, 0.76, 1.12, 0.9, 1.0, 0.72, 1.08, 0.88];
  return values[index % values.length];
}

function drawSparks() {
  for (const spark of state.sparks) {
    ctx.globalAlpha = clamp(spark.life * 2, 0, 1);
    ctx.fillStyle = spark.color;
    ctx.beginPath();
    ctx.arc(spark.x, spark.y, spark.radius, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.globalAlpha = 1;
}

function draw() {
  const shakeX = state.shake > 0 ? random(-6, 6) * state.shake * 4 : 0;
  const shakeY = state.shake > 0 ? random(-5, 5) * state.shake * 4 : 0;

  ctx.save();
  ctx.translate(shakeX, shakeY);
  drawBackground();
  drawShots();
  for (const rock of state.rocks) {
    drawRock(rock);
  }
  for (const enemy of state.enemies) {
    drawEnemy(enemy);
  }
  drawSparks();
  if (state.player) {
    drawPlayer();
  }
  ctx.restore();
}

let lastFrame = performance.now();
function frame(now) {
  const dt = Math.min((now - lastFrame) / 1000, 0.033);
  lastFrame = now;
  update(dt);
  draw();
  requestAnimationFrame(frame);
}

function bindHoldButton(selector, key) {
  const button = document.querySelector(selector);
  const setPressed = (pressed) => {
    touch[key] = pressed;
  };

  button.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    button.setPointerCapture(event.pointerId);
    setPressed(true);
  });
  button.addEventListener("pointerup", () => setPressed(false));
  button.addEventListener("pointercancel", () => setPressed(false));
  button.addEventListener("pointerleave", () => setPressed(false));
}

window.addEventListener("resize", resizeCanvas);
window.addEventListener("keydown", (event) => {
  if (["ArrowLeft", "ArrowRight", "ArrowUp", "Space", "KeyA", "KeyD", "KeyW"].includes(event.code)) {
    event.preventDefault();
    keys.add(event.code);
  }

  if (!state.running && (event.code === "Enter" || event.code === "Space")) {
    resetGame();
  }
});

window.addEventListener("keyup", (event) => {
  keys.delete(event.code);
});

startButton.addEventListener("click", resetGame);
bindHoldButton("#leftButton", "left");
bindHoldButton("#rightButton", "right");
bindHoldButton("#fireButton", "fire");

resizeCanvas();
seedStars();
state.player = makePlayer();
updateHud();
requestAnimationFrame(frame);
