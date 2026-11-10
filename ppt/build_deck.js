// 灵眸路演 PPT 骨架生成器
// 用法：NODE_PATH=<装了 pptxgenjs 的 node_modules> node build_deck.js [只生成第几页]
// 风格参考 iChoose 路演稿：仿 macOS 备忘录窗口，左侧 5 张章节卡片导航。
// 素材在 assets/（裁好的图在 assets/slot/）。灰色虚线框只剩 V3、V4 两个视频位。
const pptxgen = require("pptxgenjs");
const path = require("path");

const ONLY = process.argv[2] ? Number(process.argv[2]) : null;
const OUT = process.argv[3] || path.join(__dirname, "灵眸-路演.pptx");

const HEAD = "宋体";
const BODY = "微软雅黑";
const COL = {
  text: "1F1F1F", sub: "6B6B6B", line: "E3E3E3", card: "D4D4D4",
  hi: "FEBC30", phFill: "F4F4F5", phLine: "A1A1AA",
  red: "C8102E",
  // Napkin 风格浅色块
  blue: ["DCE7FD", "3B6FD8"], green: ["CFF5E1", "1F9D61"], lime: ["E9F7C4", "6E8F12"],
  sky: ["D3F1FB", "1386A8"], purple: ["E6E0FB", "6A4FC8"], pink: ["FBE1EA", "C23B6B"],
  peach: ["FDE9DA", "C2621F"],
};

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5
pres.title = "灵眸 · AI + 文化 路演";
pres.theme = { headFontFace: HEAD, bodyFontFace: BODY };

const CHAPTERS = [
  ["产品介绍", "灵眸是谁"],
  ["Demo 展示", "看它演"],
  ["技术设计", "看懂 · 选择 · 演出"],
  ["制作流程", "从零到一"],
  ["未来展望", "从 L1 到 L3"],
];

let pageNo = 0;
const slides = [];
function page(chapter, build, notes) { slides.push({ chapter, build, notes }); }

// ---------- 通用部件 ----------
function chrome(s, active) {
  // 红黄绿三个圆点
  [["FF5F57", 0.95], ["FEBC2E", 1.17], ["28C840", 1.39]].forEach(([c, x], i) =>
    s.addShape(pres.shapes.OVAL, { x, y: 0.6, w: 0.15, h: 0.15, fill: { color: c }, line: { color: c }, objectName: `dot${i}` }));
  // 工具栏：只画几个灰色小图形，不抢戏
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 1.75, y: 0.55, w: 0.25, h: 0.25, rectRadius: 0.04, fill: { color: "EFEFEF" }, line: { color: "EFEFEF" } });
  for (let i = 0; i < 3; i++)
    s.addShape(pres.shapes.LINE, { x: 1.8, y: 0.61 + i * 0.065, w: 0.15, h: 0, line: { color: "8A8A8A", width: 0.75 } });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 2.15, y: 0.56, w: 0.22, h: 0.22, rectRadius: 0.03, fill: { color: "FFFFFF" }, line: { color: "9A9A9A", width: 0.75 } });
  s.addText("Aa", { x: 4.1, y: 0.47, w: 0.6, h: 0.4, fontFace: "Arial", fontSize: 16, color: "8A8A8A", margin: 0, isTextBox: true });
  [11.35, 11.75, 12.15].forEach((x) =>
    s.addShape(pres.shapes.OVAL, { x, y: 0.56, w: 0.22, h: 0.22, fill: { color: "FFFFFF" }, line: { color: "9A9A9A", width: 0.75 } }));
  // 分隔线
  s.addShape(pres.shapes.LINE, { x: 0.8, y: 1.05, w: 11.85, h: 0, line: { color: COL.line, width: 1 } });
  s.addShape(pres.shapes.LINE, { x: 3.35, y: 1.05, w: 0, h: 6.0, line: { color: COL.line, width: 1 } });
  // 左侧章节卡片
  CHAPTERS.forEach(([t, sub], i) => {
    const y = 1.3 + i * 1.1, on = i + 1 === active;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: 0.95, y, w: 2.2, h: 0.9, rectRadius: 0.06,
      fill: { color: on ? COL.hi : "FFFFFF" }, line: { color: on ? COL.hi : COL.card, width: 1 },
      objectName: `chapter${i + 1}`,
    });
    s.addText([
      { text: t, options: { fontFace: HEAD, fontSize: 17, bold: true, color: COL.text, breakLine: true } },
      { text: sub, options: { fontFace: BODY, fontSize: 11, color: on ? COL.text : COL.sub } },
    ], { x: 1.2, y: y + 0.08, w: 1.9, h: 0.74, margin: 0, valign: "middle", isTextBox: true });
  });
  // 页码
  s.addText(String(pageNo), { x: 12.15, y: 6.95, w: 0.5, h: 0.3, fontSize: 10, color: "A0A0A0", align: "right", margin: 0, isTextBox: true });
}

function title(s, t, sub) {
  s.addText(t, { x: 3.75, y: 1.3, w: 8.9, h: 0.6, fontFace: HEAD, fontSize: 28, bold: true, color: COL.text, margin: 0, valign: "middle", isTextBox: true, objectName: "title" });
  if (sub) s.addText(sub, { x: 3.75, y: 1.9, w: 8.9, h: 0.35, fontSize: 13, color: COL.sub, margin: 0, isTextBox: true });
}

// 预留位：灰色虚线框，写明编号、内容和拍摄要求
function ph(s, id, kind, what, how, x, y, w, h) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x, y, w, h, rectRadius: 0.08, fill: { color: COL.phFill },
    line: { color: COL.phLine, width: 1.25, dashType: "dash" }, objectName: `PH-${id}`,
  });
  const icon = kind === "视频" ? "▶" : kind === "截图" ? "▭" : "◉";
  const big = w >= 1.8 && h >= 1.6;
  s.addText([
    { text: big ? `${icon}  ${id} · ${kind}` : `${icon} ${id}`, options: { fontSize: big ? 15 : 12, bold: true, color: "52525B", breakLine: true } },
    { text: what, options: { fontSize: big ? 12 : 10, color: "52525B", breakLine: !!how } },
    ...(how ? [{ text: how, options: { fontSize: 10, color: "8A8A93" } }] : []),
  ], { x: x + 0.12, y: y + 0.08, w: w - 0.24, h: h - 0.16, align: "center", valign: "middle", margin: 0, isTextBox: true, objectName: `PH-${id}-label` });
}

const fs = require("fs");
const SLOT = (id) => path.join(__dirname, "assets/slot", id + ".jpg");
function img(s, id, x, y, w, h, tag) {
  s.addImage({ path: SLOT(id), x, y, w, h, objectName: id, rounding: false });
  if (tag) {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x + 0.12, y: y + h - 0.45, w: 1.3, h: 0.32, rectRadius: 0.16, fill: { color: "000000", transparency: 40 }, line: { color: "000000", transparency: 100 } });
    s.addText(tag, { x: x + 0.12, y: y + h - 0.45, w: 1.3, h: 0.32, fontSize: 10, color: "FFFFFF", align: "center", valign: "middle", margin: 0, isTextBox: true });
  }
}
function vid(s, file, cover, x, y, w, h) {
  const c = "data:image/jpeg;base64," + fs.readFileSync(path.join(__dirname, "assets", cover)).toString("base64");
  s.addMedia({ type: "video", path: path.join(__dirname, "assets", file), cover: c, x, y, w, h, objectName: file });
}
function card(s, x, y, w, h, [bg, fg], head, body, opts = {}) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.1, fill: { color: bg }, line: { color: bg } });
  s.addText([
    { text: head, options: { fontFace: HEAD, fontSize: opts.hs || 17, bold: true, color: fg, breakLine: true } },
    { text: body, options: { fontSize: opts.bs || 13, color: "3A3A3A" } },
  ], { x: x + 0.2, y: y + 0.12, w: w - 0.4, h: h - 0.24, margin: 0, valign: opts.valign || "top", paraSpaceAfter: 4, isTextBox: true });
}

function arrow(s, x, y, w) {
  s.addShape(pres.shapes.LINE, { x, y, w, h: 0, line: { color: "9A9A9A", width: 1.5, endArrowType: "triangle" } });
}

// ---------- 1 产品介绍 ----------
page(0, (s) => {
  s.addText("灵眸", { x: 3.75, y: 2.0, w: 4.6, h: 1.3, fontFace: HEAD, fontSize: 66, bold: true, color: COL.text, margin: 0, isTextBox: true });
  s.addText("会看戏，也会用眼神回应你的机器人头", { x: 3.75, y: 3.35, w: 4.8, h: 0.9, fontFace: HEAD, fontSize: 20, bold: true, color: COL.text, margin: 0, valign: "top", isTextBox: true });
  s.addText("看懂京剧脸谱，用 21 个舵机演出眼神程式", { x: 3.75, y: 3.95, w: 4.6, h: 0.4, fontSize: 14, color: COL.sub, margin: 0, isTextBox: true });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 3.75, y: 5.25, w: 1.5, h: 0.42, rectRadius: 0.21, fill: { color: COL.hi }, line: { color: COL.hi } });
  s.addText("AI + 文化", { x: 3.75, y: 5.25, w: 1.5, h: 0.42, fontSize: 13, bold: true, color: COL.text, align: "center", valign: "middle", margin: 0, isTextBox: true });
  s.addText("灵眸队 · 2026.11.08 决赛路演", { x: 5.45, y: 5.25, w: 3.0, h: 0.42, fontSize: 12, color: COL.sub, valign: "middle", margin: 0, isTextBox: true });
  img(s, "P1", 8.7, 1.35, 3.9, 5.4, "装配模型渲染");
}, "【约 20 秒】我们是灵眸队。灵眸是一个会看戏、也会用眼神回应你的机器人头。");

page(1, (s) => {
  title(s, "一身之戏在于脸，一脸之戏在于眼", "戏曲谚语");
  const items = [
    [COL.blue, "程式难懂", "脸谱颜色、眼神、亮相都有一套程式，年轻观众看不出门道"],
    [COL.peach, "AI 停在屏幕里", "AI 能生成图片和视频，但没有一个在场、能和你对视的表演者"],
    [COL.green, "我们的回答", "让 AI 看懂脸谱，再用一张实体的脸，把眼神程式演给你看"],
  ];
  items.forEach(([c, h, b], i) => card(s, 3.75, 2.45 + i * 1.45, 4.5, 1.25, c, h, b));
  img(s, "P2", 8.55, 2.45, 4.05, 4.15);
}, "【约 35 秒】戏曲行里说，一身之戏在于脸，一脸之戏在于眼。但脸谱和眼神的程式，年轻人很难看懂。今天的 AI 能生成图片、视频，却始终停在屏幕里。我们想让 AI 看懂脸谱，再用一张真实的脸演出来。");

page(1, (s) => {
  title(s, "灵眸是什么", "21 个舵机的仿生头 + 多模态大模型 + 戏曲表情程式库");
  img(s, "P3", 3.75, 2.45, 3.3, 4.2, "真机实拍");
  const modes = [
    [COL.pink, "看戏", "给一张脸谱，它判断行当和情绪，演出对应程式"],
    [COL.blue, "看见你", "眼睛跟着观众走，离得远近不同，表情也不同"],
    [COL.green, "听你说", "和它对话，它带着情绪回答，下巴跟着说话动"],
    [COL.purple, "学你", "你对着摄像头做表情，灵眸看着你学出来"],
  ];
  modes.forEach(([c, h, b], i) => card(s, 7.3 + (i % 2) * 2.7, 2.45 + Math.floor(i / 2) * 2.15, 2.55, 1.95, c, h, b));
}, "【约 35 秒】灵眸由三部分组成：21 个舵机驱动的仿生头，多模态大模型，以及我们整理的戏曲表情程式库。它有四种玩法：看戏、看见你、听你说、学你。下面直接看视频。");

// ---------- 2 Demo 展示 ----------
page(2, (s) => {
  title(s, "灵眸，开演");
  vid(s, "V1_主视频.mp4", "V1_cover.jpg", 3.9, 2.05, 8.53, 4.8);
}, "【视频 66 秒，播放时不讲话，点击播放】\n0–15s 看戏：红脸、黑脸、蓝脸依次演出；15–66s 学你：摄像头看人的表情，灵眸跟着学。");

page(2, (s) => {
  title(s, "看戏：看懂脸谱，演出程式");
  const cols = [["动作", 3.75, 1.75], ["脸谱原图", 5.65, 2.0], ["2D 预览", 7.8, 2.0], ["真机", 9.95, 2.65]];
  cols.forEach(([t, x, w]) => s.addText(t, { x, y: 2.0, w, h: 0.3, fontSize: 12, bold: true, color: COL.sub, align: t === "动作" ? "left" : "center", margin: 0, isTextBox: true }));
  const rows = [
    ["威严亮相", "红脸 · 忠勇", COL.pink, "P4", "红脸", "V2a_红脸"],
    ["怒目圆睁", "黑脸 · 刚直", COL.purple, "P5", "黑脸", "V2b_黑脸"],
    ["横眉瞪视", "蓝脸 · 刚强", COL.blue, "P6", "蓝脸", "V2c_蓝脸"],
  ];
  rows.forEach(([n, d, c, p, k, v], i) => {
    const y = 2.4 + i * 1.46;
    card(s, 3.75, y, 1.75, 1.33, c, n, d, { hs: 16, bs: 12, valign: "middle" });
    img(s, p, 5.65, y, 2.0, 1.33);
    img(s, `S2_${k}`, 7.8, y, 2.0, 1.33);
    vid(s, `${v}.mp4`, `${v}_cover.jpg`, 9.95, y, 2.65, 1.33);
  });
}, "【约 35 秒】同一个动作的三种形态：脸谱原图、2D 预览、真机演出（右列视频点击播放）。红脸忠勇，所以威严亮相；黑脸刚直，所以怒目圆睁；蓝脸刚强，所以横眉瞪视。");

page(2, (s) => {
  title(s, "学你、看见你，也听你说");
  vid(s, "V5_学你.mp4", "V5_学你_cover.jpg", 3.75, 2.15, 5.2, 2.93);
  card(s, 3.75, 5.3, 5.2, 1.35, COL.purple, "学你：表情实时模仿", "摄像头识别你的表情，2D 脸和真机一起学出来", { hs: 16, bs: 13 });
  ph(s, "V3", "视频", "看见你", "人左右走 + 突然贴近", 9.15, 2.15, 3.45, 1.94);
  s.addText("看见你：眼神跟随，距离不同表情不同", { x: 9.15, y: 4.13, w: 3.45, h: 0.3, fontSize: 11, color: COL.sub, margin: 0, isTextBox: true });
  ph(s, "V4", "视频", "听你说", "一句完整对话 · 加字幕", 9.15, 4.5, 3.45, 1.94);
  s.addText("听你说：回复 1.38 s，下巴跟着说话动", { x: 9.15, y: 6.48, w: 3.45, h: 0.3, fontSize: 11, color: COL.sub, margin: 0, isTextBox: true });
}, "【约 35 秒】左边是现场实拍的“学你”：你做表情，它跟着学。灵眸没有脖子，注意力全靠眼神。它会一直看着你，离得太近会皱眉、害怕。和它说话时，表情跟着回答的情绪走，下巴跟着声音动，眼睛仍然看着你。");

// ---------- 3 技术设计 ----------
page(3, (s) => {
  title(s, "看懂 → 选择 → 演出", "所有输入汇到一个控制进程，按优先级合成后才驱动舵机");
  const cols = [
    [COL.blue, "输入", "脸谱图片\n摄像头\n麦克风"],
    [COL.green, "看懂", "千问 Omni：行当与情绪\n视觉：人的位置与距离\nMiniMax：对话与情绪"],
    [COL.lime, "选择", "文化程式库\n16 段动作\n京剧 7 · 动漫 9"],
    [COL.purple, "合成", "统一控制进程\n50 Hz 分层合成\n失联保护"],
    [COL.peach, "演出", "3 块 Pico\n21 个舵机\n眼 · 眉 · 嘴"],
  ];
  const w = 1.45, gap = 0.35;
  cols.forEach(([c, h, b], i) => {
    const x = 3.75 + i * (w + gap);
    card(s, x, 2.5, w, 2.35, c, h, b, { hs: 17, bs: 11 });
    if (i < cols.length - 1) arrow(s, x + w + 0.05, 3.67, gap - 0.1);
  });
  s.addText("合成优先级", { x: 3.75, y: 5.2, w: 2, h: 0.35, fontFace: HEAD, fontSize: 15, bold: true, color: COL.text, margin: 0, isTextBox: true });
  const layers = ["安全", "眨眼", "手动", "嘴型", "对话情绪", "距离情绪", "待机"];
  let x = 3.75;
  layers.forEach((t, i) => {
    const lw = t.length > 2 ? 1.1 : 0.78;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 5.75, w: lw, h: 0.5, rectRadius: 0.25, fill: { color: i === 0 ? COL.hi : "F1F1F1" }, line: { color: i === 0 ? COL.hi : "F1F1F1" } });
    s.addText(t, { x, y: 5.75, w: lw, h: 0.5, fontSize: 12, bold: i === 0, color: COL.text, align: "center", valign: "middle", margin: 0, isTextBox: true });
    x += lw;
    if (i < layers.length - 1) { s.addText(">", { x, y: 5.75, w: 0.3, h: 0.5, fontSize: 13, color: "9A9A9A", align: "center", valign: "middle", margin: 0, isTextBox: true }); x += 0.3; }
  });
}, "【约 35 秒】技术上分三步：看懂、选择、演出。图片交给千问 Omni 判断行当和情绪，摄像头算人的位置和距离，语音走 MiniMax。结果映射到文化程式库里的动作，再交给唯一的控制进程，以 50 Hz 按优先级合成，最后由 3 块 Pico 驱动 21 个舵机。");

page(3, (s) => {
  title(s, "文化程式库：把脸谱翻译成舵机动作");
  const hdr = { bold: true, color: COL.text, fill: { color: "F1F1F1" } };
  const rows = [
    ["脸谱 / 行当", "人物气质", "动作"],
    ["红脸", "忠勇威严", "威严亮相"],
    ["黑脸", "刚直勇猛", "怒目圆睁"],
    ["白脸", "奸诈多疑", "斜眼冷笑"],
    ["蓝脸 · 绿脸", "刚强桀骜", "横眉瞪视"],
    ["金脸 · 银脸", "神佛庄严", "庄严垂目"],
    ["旦角", "婉约含情", "眼波流转"],
    ["丑角", "诙谐灵活", "挤眉弄眼"],
  ].map((r, i) => r.map((t) => ({ text: t, options: i === 0 ? hdr : { color: "3A3A3A" } })));
  s.addTable(rows, { x: 3.75, y: 2.15, w: 4.6, colW: [1.55, 1.5, 1.55], rowH: 0.56, fontSize: 14, fontFace: BODY, border: { type: "solid", color: COL.line, pt: 0.75 }, valign: "middle", margin: [0, 0.12, 0, 0.12] });
  s.addImage({ path: path.join(__dirname, "assets/S4_演示页看戏.png"), x: 8.6, y: 2.15, w: 4.0, h: 2.26, objectName: "S4" });
  card(s, 8.6, 4.65, 4.0, 1.3, COL.pink, "每个动作是一串关键帧", "如“亮相”：垂目蓄势 → 缓缓抬眼 → 定格", { hs: 15, bs: 12, valign: "middle" });
}, "【约 30 秒】我们把行当和脸谱整理成 7 段京剧动作，另有 9 段动漫表情。每段动作是一串关键帧，比如亮相：先垂目蓄势，再缓缓抬眼，最后定格。\n（备注：动作是按公开的行当常识编排的，若有戏曲专业人士审阅过，在这里补一句。）");

page(3, (s) => {
  title(s, "可靠，才能上台");
  const stats = [["21", "个舵机 · 3 块 Pico"], ["50 Hz", "控制循环"], ["1 s", "失联回待机，3 s 全部卸力"], ["260", "项自动化测试"]];
  stats.forEach(([n, l], i) => {
    const x = 3.75 + i * 2.25;
    s.addText(n, { x, y: 2.2, w: 2.1, h: 0.8, fontFace: "Arial", fontSize: 40, bold: true, color: COL.text, margin: 0, isTextBox: true });
    s.addText(l, { x, y: 3.0, w: 2.1, h: 0.55, fontSize: 12, color: COL.sub, margin: 0, valign: "top", isTextBox: true });
  });
  img(s, "S5", 3.75, 3.85, 5.0, 2.8);
  ["一个进程独占硬件，避免抢串口", "只驱动已标定的舵机，下巴成对约束", "六种模式一键切换，Esc 全部卸力", "识图小样本：22 张图类别全对"].forEach((t, i) => {
    const y = 3.95 + i * 0.62;
    s.addShape(pres.shapes.OVAL, { x: 9.0, y: y + 0.12, w: 0.14, h: 0.14, fill: { color: COL.hi }, line: { color: COL.hi } });
    s.addText(t, { x: 9.3, y, w: 3.3, h: 0.4, fontSize: 14, color: "3A3A3A", valign: "middle", margin: 0, isTextBox: true });
  });
}, "【约 30 秒】为了上台不出事故，我们只让一个进程管硬件。程序崩溃 1 秒内回到待机，3 秒全部卸力。整个系统有 260 项自动化测试。\n（实际是 260 项里 259 项通过，被问到时如实说。识图测试只有 22 张，是小样本。）");

// ---------- 4 制作流程 ----------
page(4, (s) => {
  title(s, "从一卷耗材到一张会演戏的脸");
  const steps = [
    ["P7", "3D 打印", "头骨、眼、眉、嘴全部零件"],
    ["P8", "焊接", "嘴部板与眼眉板"],
    ["P9", "组装", "眼、眉、嘴三大机构装进头骨"],
    ["P10", "标定", "21 个舵机逐个回中、测范围"],
    ["P11", "联调", "控制进程、戏台、视觉、语音"],
  ];
  const w = 1.6, gap = 0.21;
  s.addShape(pres.shapes.LINE, { x: 3.75 + w / 2, y: 4.75, w: 4 * (w + gap), h: 0, line: { color: COL.card, width: 1.5 } });
  steps.forEach(([id, h, b], i) => {
    const x = 3.75 + i * (w + gap);
    img(s, id, x, 2.3, w, 2.1);
    s.addShape(pres.shapes.OVAL, { x: x + w / 2 - 0.13, y: 4.62, w: 0.26, h: 0.26, fill: { color: COL.hi }, line: { color: "FFFFFF", width: 2 } });
    s.addText([
      { text: `${i + 1}  ${h}`, options: { fontFace: HEAD, fontSize: 16, bold: true, color: COL.text, breakLine: true } },
      { text: b, options: { fontSize: 12, color: COL.sub } },
    ], { x, y: 5.05, w, h: 1.4, margin: 0, valign: "top", align: "left", isTextBox: true });
  });
}, "【约 30 秒】机械结构基于开源设计，我们从打印零件开始，自己焊了控制板，装好眼、眉、嘴三大机构，把 21 个舵机逐个标定，再写控制进程、戏台、视觉和语音。");

// ---------- 5 未来展望 ----------
page(5, (s) => {
  title(s, "从 L1 到 L3");
  const lv = [
    [COL.green, "L1 看图演", "已完成", "给一张脸谱，演出对应程式"],
    [COL.blue, "L2 互动观演", "进行中", "观众做表情，它用程式回应；多人时锁定一位观众"],
    [COL.purple, "L3 走进剧场与课堂", "下一步", "戏曲馆导览、戏曲进校园、表情程式教学"],
  ];
  lv.forEach(([c, h, tag, b], i) => {
    const x = 3.75 + i * 2.98, y = 4.4 - i * 1.0, hh = 2.3 + i * 1.0;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 2.78, h: hh, rectRadius: 0.1, fill: { color: c[0] }, line: { color: c[0] } });
    s.addText([
      { text: tag, options: { fontSize: 11, bold: true, color: c[1], breakLine: true } },
      { text: h, options: { fontFace: HEAD, fontSize: 18, bold: true, color: c[1], breakLine: true } },
      { text: b, options: { fontSize: 13, color: "3A3A3A" } },
    ], { x: x + 0.2, y: y + 0.15, w: 2.38, h: 1.9, margin: 0, valign: "top", paraSpaceAfter: 4, isTextBox: true });
  });
  img(s, "P14", 3.75, 2.35, 2.78, 1.8, "比赛现场");
}, "【约 25 秒】L1 看图演已经完成；L2 是观众互动，你做表情，它用程式回应；L3 希望走进戏曲馆和课堂，做导览和程式教学。");

page(5, (s) => {
  title(s, "灵眸队");
  for (let i = 0; i < 4; i++) {
    const x = 3.75 + i * 2.25;
    s.addShape(pres.shapes.OVAL, { x: x + 0.45, y: 2.2, w: 1.2, h: 1.2, fill: { color: [COL.blue, COL.green, COL.pink, COL.purple][i][0] }, line: { color: "FFFFFF" } });
    s.addText(String(i + 1), { x: x + 0.45, y: 2.2, w: 1.2, h: 1.2, fontFace: HEAD, fontSize: 30, bold: true, color: [COL.blue, COL.green, COL.pink, COL.purple][i][1], align: "center", valign: "middle", margin: 0, isTextBox: true });
    s.addText([
      { text: "成员姓名", options: { fontFace: HEAD, fontSize: 16, bold: true, color: COL.text, breakLine: true } },
      { text: "分工 · 一句话亮点", options: { fontSize: 12, color: COL.sub } },
    ], { x, y: 3.55, w: 2.1, h: 0.8, align: "center", margin: 0, isTextBox: true });
  }
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 3.75, y: 4.7, w: 8.85, h: 1.95, rectRadius: 0.08, fill: { color: "F7F7F7" }, line: { color: "F7F7F7" } });
  s.addText([
    { text: "致谢与署名", options: { fontFace: HEAD, fontSize: 15, bold: true, color: COL.text, breakLine: true } },
    { text: "机械结构基于 Will Cogley 的开源设计 Robot Head α2.0.33 与 EyeMech ε3.2（CC BY-NC-SA 4.0）。我们在此基础上完成电路、固件、控制系统、AI 与文化动作库。", options: { fontSize: 12, color: "3A3A3A", breakLine: true } },
    { text: "脸谱图片来自 Wikimedia Commons（Shizhao，CC BY 3.0；Jnzl's Photos，CC BY 2.0 等）。", options: { fontSize: 12, color: "3A3A3A", breakLine: true } },
    { text: "下午 12:30–18:00，B3 楼现场展示，欢迎来和灵眸对视。", options: { fontSize: 13, bold: true, color: COL.red } },
  ], { x: 4.0, y: 4.85, w: 8.35, h: 1.7, margin: 0, valign: "top", paraSpaceAfter: 5, isTextBox: true });
}, "【约 15 秒】我们是灵眸队。感谢 Will Cogley 的开源设计。下午 B3 楼现场展示，欢迎来和灵眸对视。");

// ---------- 输出 ----------
slides.forEach((p, i) => {
  pageNo = i + 1;
  if (ONLY && ONLY !== pageNo) return;
  const s = pres.addSlide();
  s.background = { color: "FFFFFF" };
  chrome(s, p.chapter);
  p.build(s);
  s.addNotes(p.notes);
});

pres.writeFile({ fileName: OUT }).then(() => console.log("wrote", OUT));
