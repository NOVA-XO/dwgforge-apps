/* Blender маягийн 3D үзүүлэлт — цэвэр WebGL, гуравдагч этгээдийн сангүй.
 *
 * Юуг Blender-ээс авав:
 *   · эргүүлэгч ширээний навигаци (тойруулах / зөөх / ойртуулах), numpad товчлол
 *   · шалны адаптив тор, X/Y тэнхлэгийн улаан/ногоон шугам
 *   · баруун дээд булангийн тэнхлэгийн gizmo — товшиход харагдац үсэрнэ
 *   · сүүдэрлэлтийн горимууд: утсан загвар / битүү / материал
 *   · N товчоор нээгдэх хажуугийн самбар, доод талын товчлолын мөр
 *
 * Меш нь AutoCAD-ын STLOUT-аас ирнэ (mesh.py). STL нь зөвхөн гурвалжин
 * дамжуулдаг тул нормалийг энд бодно: Blender-ийн "Shade Auto Smooth" шиг
 * 30 хэмийн дотор зэргэлдээ талуудыг гөлгөрүүлж, хурц ирмэгийг нь хэвээр
 * үлдээнэ. Ингэснээр цилиндр гөлгөр, ирмэг нь тод харагдана.
 */

window.VP = (function () {
  'use strict';

  // ------------------------------------------------------------------
  // Тогтмолууд
  // ------------------------------------------------------------------

  const VIEW_BG = [0.224, 0.224, 0.224];        // Blender-ийн #393939
  const MAT_BG = [0.145, 0.153, 0.170];         // материалын горимын орчин
  const OBJ_GRAY = [0.73, 0.73, 0.73];          // Blender-ийн өгөгдмөл биетийн өнгө
  const OBJ_STEEL = [0.60, 0.63, 0.68];         // материалын горим — ган
  const WIRE_COL = [0.055, 0.055, 0.055, 1];    // утсан загварын ирмэг

  const SMOOTH_ANGLE = 30;                       // Blender-ийн өгөгдмөл auto smooth
  const FOV = (39.6 * Math.PI) / 180;            // 50 мм линз
  const DEG = Math.PI / 180;

  // Тэнхлэгийн харагдац -> (азимут, өндрийн өнцөг) хэмээр. Азимут 0 = урдаас.
  const AXIS_VIEWS = {
    front: [0, 0], back: [180, 0], right: [-90, 0],
    left: [90, 0], top: [0, 90], bottom: [0, -90],
  };
  const VIEW_MN = {
    front: 'Урдаас', back: 'Араас', right: 'Баруунаас', left: 'Зүүнээс',
    top: 'Дээрээс', bottom: 'Доороос', user: 'Чөлөөт',
  };

  // AutoCAD-ын нэрлэсэн харагдацууд — F12 рендерт хамгийн ойрыг нь сонгоно.
  const ACAD_VIEWS = [
    { key: 'swiso', dir: [-1, -1, 1] }, { key: 'seiso', dir: [1, -1, 1] },
    { key: 'neiso', dir: [1, 1, 1] }, { key: 'nwiso', dir: [-1, 1, 1] },
    { key: 'top', dir: [0, 0, 1] }, { key: 'front', dir: [0, -1, 0] },
    { key: 'right', dir: [1, 0, 0] },
  ];

  // ------------------------------------------------------------------
  // Матрицууд (WebGL-ийн заншлаар баганын дараалал)
  // ------------------------------------------------------------------

  function perspective(out, fovy, aspect, near, far) {
    const f = 1 / Math.tan(fovy / 2);
    out.fill(0);
    out[0] = f / aspect; out[5] = f; out[11] = -1;
    out[10] = (far + near) / (near - far);
    out[14] = (2 * far * near) / (near - far);
  }

  function orthographic(out, height, aspect, near, far) {
    out.fill(0);
    out[0] = 2 / (height * aspect); out[5] = 2 / height;
    out[10] = -2 / (far - near); out[14] = -(far + near) / (far - near);
    out[15] = 1;
  }

  /* Эргүүлэгч ширээний харагдацын матриц: R = Rx(el - 90°) · Rz(az), дараа нь
   * камерыг байнаас `dist` зайд ухраана. az = 0, el = 0 үед камер -Y дээрээс
   * +Y тийш харна (Blender-ийн Front) бөгөөд дэлхийн +Z нь дэлгэцийн дээш болно.
   * Буцаах утга: R-ийн мөрүүд = камерын баруун / дээш / хойш тэнхлэг. */
  function viewMatrix(out, az, el, dist, target) {
    const ca = Math.cos(az), sa = Math.sin(az);
    const ct = Math.cos(el - Math.PI / 2), st = Math.sin(el - Math.PI / 2);
    const r = [
      [ca, -sa, 0],
      [ct * sa, ct * ca, -st],
      [st * sa, st * ca, ct],
    ];
    for (let i = 0; i < 3; i++) {
      out[i] = r[i][0]; out[4 + i] = r[i][1]; out[8 + i] = r[i][2];
      out[12 + i] = -(r[i][0] * target[0] + r[i][1] * target[1] + r[i][2] * target[2]);
    }
    out[14] -= dist;
    out[3] = out[7] = out[11] = 0; out[15] = 1;
    return r;
  }

  // ------------------------------------------------------------------
  // Шейдерүүд
  // ------------------------------------------------------------------

  const MESH_VS = `
    attribute vec3 aPos;
    attribute vec3 aNrm;
    uniform mat4 uProj, uView;
    varying vec3 vN, vP;
    void main() {
      vec4 p = uView * vec4(aPos, 1.0);
      vP = p.xyz;
      vN = mat3(uView) * aNrm;
      gl_Position = uProj * p;
    }`;

  /* Гэрэл нь ХАРАГДАЦЫН огторгуйд суурилсан — камер эргэхэд гэрэл дагаж эргэнэ.
   * Blender-ийн Solid горимын "Studio" гэрэлтүүлгийн гол шинж нь тэр.
   * uFlat = 1 үед гэрэлтүүлэггүй, зөвхөн өнгө: утсан загварын үед биетийг
   * дэвсгэрийн өнгөөр дүүргэж далд ирмэгийг нуухад хэрэглэнэ. */
  const MESH_FS = `
    precision mediump float;
    varying vec3 vN, vP;
    uniform vec3 uAlbedo;
    uniform float uMetal, uFlat;
    void main() {
      if (uFlat > 0.5) { gl_FragColor = vec4(uAlbedo, 1.0); return; }
      vec3 n = normalize(vN);
      if (!gl_FrontFacing) n = -n;
      vec3 v = normalize(-vP);
      vec3 l1 = normalize(vec3(-0.30, 0.60, 0.75));
      vec3 l2 = normalize(vec3( 0.75, 0.25, 0.45));
      vec3 l3 = normalize(vec3( 0.10, -0.85, 0.20));
      float d1 = max(dot(n, l1), 0.0);
      float d2 = max(dot(n, l2), 0.0);
      float d3 = max(dot(n, l3), 0.0);
      vec3 diff = uAlbedo * (0.26 + 0.70 * d1 + 0.32 * d2 + 0.13 * d3);
      float sh = mix(26.0, 80.0, uMetal);
      float s1 = pow(max(dot(reflect(-l1, n), v), 0.0), sh);
      float s2 = pow(max(dot(reflect(-l2, n), v), 0.0), sh);
      vec3 spec = vec3(0.9) * (s1 * mix(0.16, 0.55, uMetal) + s2 * mix(0.07, 0.28, uMetal));
      float fres = pow(1.0 - max(dot(n, v), 0.0), 4.0);
      vec3 env = mix(vec3(0.16, 0.18, 0.22), vec3(0.74, 0.78, 0.86), n.y * 0.5 + 0.5);
      vec3 col = mix(diff, diff * 0.42 + env * uAlbedo * 1.05, uMetal);
      gl_FragColor = vec4(col + spec + fres * mix(0.04, 0.15, uMetal), 1.0);
    }`;

  /* Утсан загварын ирмэгүүд. Эдгээр нь эд ангийн хэмжээтэй богино хэрчмүүд
   * тул шууд зурж болно. */
  const LINE_VS = `
    attribute vec3 aPos;
    attribute vec4 aCol;
    uniform mat4 uProj, uView;
    uniform float uAlpha;
    varying vec4 vCol;
    void main() {
      vCol = vec4(aCol.rgb, aCol.a * uAlpha);
      gl_Position = uProj * uView * vec4(aPos, 1.0);
    }`;

  const LINE_FS = `
    precision mediump float;
    varying vec4 vCol;
    void main() { gl_FragColor = vCol; }`;

  /* Тор нь ХОЁР ГУРВАЛЖИН — шугам биш.
   *
   * Уртаа хэдэн мянган нэгж болсон шугам камерын хавтгайг огтлоход ойрын
   * хавтгайд таслагдаад дэлгэцийн координат нь зуун мянган пиксел болдог.
   * Тэр нь растержуулагчийн хамгаалалтын зурваснаас хальж, GPU шугамыг бүхэлд
   * нь хаядаг — тор огт харагдахгүй. Blender ч мөн адил шалтгаанаар торыг
   * шейдерээр зурдаг. Хавтгай дөрвөлжин дээр хээг нь фрагмент бүрээр бодоход
   * тайралтын асуудал алга, шугам нь пикселийн өргөнтэй жигд, шатгүй гарна.
   *
   * `uPersp` = 1 үед нэг пикселийн дэлхийн хэмжээ гүнтэй пропорциональ.
   * Дэлгэц дээрх нягтрал нь хэт өтгөрвөл нарийн давхаргыг бүдгэрүүлж,
   * moire-оос сэргийлнэ. */
  const GRID_VS = `
    attribute vec2 aPos;
    uniform mat4 uProj, uView;
    uniform vec2 uOrigin;
    uniform float uExtent;
    varying vec2 vXY;
    varying float vDepth;
    void main() {
      vXY = aPos * uExtent;
      vec4 p = uView * vec4(uOrigin + vXY, 0.0, 1.0);
      vDepth = -p.z;
      gl_Position = uProj * p;
    }`;

  const GRID_FS = `
    #ifdef GL_FRAGMENT_PRECISION_HIGH
    precision highp float;
    #else
    precision mediump float;
    #endif
    uniform float uStep, uPx, uPersp, uFine;
    uniform vec2 uFade, uAxis, uCenter;
    varying vec2 vXY;
    varying float vDepth;

    float band(vec2 p, float s, float w) {
      vec2 d = abs(mod(p + 0.5 * s, s) - 0.5 * s);
      return 1.0 - smoothstep(w, w * 2.0, min(d.x, d.y));
    }

    void main() {
      float px = uPx * mix(1.0, max(vDepth, 1e-4), uPersp);
      float w = px * 0.6;
      float fine = band(vXY, uStep, w) * uFine
                 * smoothstep(4.0, 13.0, uStep / max(px, 1e-6));
      float coarse = band(vXY, uStep * 10.0, w);
      float a = max(fine * 0.5, coarse * 0.72);
      vec3 col = vec3(0.36);

      vec2 ax = abs(vXY - uAxis);
      float axisX = 1.0 - smoothstep(w, w * 2.0, ax.y);   // Y = 0 -> X тэнхлэг
      float axisY = 1.0 - smoothstep(w, w * 2.0, ax.x);   // X = 0 -> Y тэнхлэг
      col = mix(col, vec3(0.85, 0.22, 0.31), axisX);
      col = mix(col, vec3(0.44, 0.76, 0.09), axisY);
      a = max(a, max(axisX, axisY) * 0.85);

      a *= 1.0 - smoothstep(uFade.x, uFade.y, distance(vXY, uCenter));
      if (a < 0.004) discard;
      gl_FragColor = vec4(col, a);
    }`;

  // ------------------------------------------------------------------
  // Төлөв
  // ------------------------------------------------------------------

  let gl = null, canvas = null, root = null, dom = {};
  let progMesh = null, progLine = null, progGrid = null;
  let bufMesh = null, bufEdge = null, bufQuad = null;
  let nEdgeVerts = 0;
  let model = null;      // {name, tris, verts, lo, hi, size}
  let raw = null;        // {m, w} — гөлгөрүүлэлтийг дахин бодоход хэрэгтэй
  let shading = 'solid', wireOverlay = false, smooth = true;
  let dirty = true, anim = null, npanelOn = true, hovering = false;
  let onRender = null;

  const cam = { az: -40 * DEG, el: 22 * DEG, dist: 600, target: [0, 0, 0], ortho: false, view: 'user' };
  const mProj = new Float32Array(16), mView = new Float32Array(16);
  let basis = [[1, 0, 0], [0, 1, 0], [0, 0, 1]];

  const requestRender = () => { dirty = true; };

  // ------------------------------------------------------------------
  // WebGL туслахууд
  // ------------------------------------------------------------------

  function compile(vsSrc, fsSrc, attrs) {
    const mk = (type, src) => {
      const s = gl.createShader(type);
      gl.shaderSource(s, src);
      gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
        throw new Error(gl.getShaderInfoLog(s) || 'шейдер хөрвүүлэгдсэнгүй');
      }
      return s;
    };
    const p = gl.createProgram();
    gl.attachShader(p, mk(gl.VERTEX_SHADER, vsSrc));
    gl.attachShader(p, mk(gl.FRAGMENT_SHADER, fsSrc));
    gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) {
      throw new Error(gl.getProgramInfoLog(p) || 'шейдер холбогдсонгүй');
    }
    const o = { p, a: {}, u: {} };
    attrs.forEach((n) => { o.a[n] = gl.getAttribLocation(p, n); });
    const nu = gl.getProgramParameter(p, gl.ACTIVE_UNIFORMS);
    for (let i = 0; i < nu; i++) {
      const nm = gl.getActiveUniform(p, i).name;
      o.u[nm] = gl.getUniformLocation(p, nm);
    }
    return o;
  }

  function upload(buf, data) {
    const b = buf || gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, b);
    gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);
    return b;
  }

  // ------------------------------------------------------------------
  // STL -> меш
  // ------------------------------------------------------------------

  function parseSTL(buf) {
    if (buf.byteLength < 84) throw new Error('STL хэт богино');
    const dv = new DataView(buf);
    const n = dv.getUint32(80, true);
    // AutoCAD үргэлж хоёртын STL бичнэ (STLOUT-д "_Y" гэж хариулсан).
    if (buf.byteLength !== 84 + n * 50) throw new Error('хоёртын STL биш байна');
    if (n === 0) throw new Error('меш хоосон — солид олдсонгүй');

    const pos = new Float32Array(n * 9);
    const fnorm = new Float32Array(n * 3);
    const lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];

    for (let i = 0; i < n; i++) {
      const o = 84 + i * 50 + 12;
      const b = i * 9;
      for (let k = 0; k < 9; k++) {
        const v = dv.getFloat32(o + k * 4, true);
        pos[b + k] = v;
        const a = k % 3;
        if (v < lo[a]) lo[a] = v;
        if (v > hi[a]) hi[a] = v;
      }
      // Нормалийг файлынхаас биш, оройноос нь бодно: зарим бичигч тэг үлдээдэг.
      const ax = pos[b + 3] - pos[b], ay = pos[b + 4] - pos[b + 1], az = pos[b + 5] - pos[b + 2];
      const bx = pos[b + 6] - pos[b], by = pos[b + 7] - pos[b + 1], bz = pos[b + 8] - pos[b + 2];
      const nx = ay * bz - az * by, ny = az * bx - ax * bz, nz = ax * by - ay * bx;
      const len = Math.hypot(nx, ny, nz) || 1;
      fnorm[i * 3] = nx / len; fnorm[i * 3 + 1] = ny / len; fnorm[i * 3 + 2] = nz / len;
    }
    return { n, pos, fnorm, lo, hi };
  }

  /* STLOUT нь мешийг эерэг октант руу шилжүүлдэг (бүх солидыг НЭГ ижил
   * вектороор, тул харилцан байрлал эвдрэхгүй). Зургийн жинхэнэ хязгаар
   * өгөгдсөн бол мешийн төвийг түүн рүү буулгаж загварчилсан байрлалд
   * нь буцаана — ингэснээр хоолой эх цэгээс эхэлж, тор нь утга агуулна. */
  function place(m, ext) {
    if (!ext) return;
    for (let i = 0; i < 3; i++) {
      const t = (ext[i] + ext[i + 3]) / 2 - (m.lo[i] + m.hi[i]) / 2;
      if (!isFinite(t)) return;
      for (let k = i; k < m.pos.length; k += 3) m.pos[k] += t;
      m.lo[i] += t; m.hi[i] += t;
    }
  }

  /* Оройг гагнаж, орой бүрийн эргэн тойрны талуудыг CSR-ээр индекслэнэ.
   * Гөлгөр нормаль ба утсан загварын ирмэг хоёулаа үүн дээр тулна. */
  function weld(m) {
    const size = Math.max(m.hi[0] - m.lo[0], m.hi[1] - m.lo[1], m.hi[2] - m.lo[2], 1);
    const q = size * 1e-5;
    const map = new Map();
    const vid = new Int32Array(m.n * 3);
    const vpos = [];
    for (let c = 0; c < m.n * 3; c++) {
      const x = m.pos[c * 3], y = m.pos[c * 3 + 1], z = m.pos[c * 3 + 2];
      const key = Math.round(x / q) + ',' + Math.round(y / q) + ',' + Math.round(z / q);
      let id = map.get(key);
      if (id === undefined) {
        id = vpos.length / 3;
        map.set(key, id);
        vpos.push(x, y, z);
      }
      vid[c] = id;
    }
    const nv = vpos.length / 3;
    const off = new Int32Array(nv + 1);
    for (let c = 0; c < vid.length; c++) off[vid[c] + 1]++;
    for (let i = 0; i < nv; i++) off[i + 1] += off[i];
    const adj = new Int32Array(vid.length);
    const fill = off.slice(0, nv);
    for (let f = 0; f < m.n; f++) {
      for (let k = 0; k < 3; k++) adj[fill[vid[f * 3 + k]]++] = f;
    }
    return { vid, vpos: new Float32Array(vpos), off, adj };
  }

  /* Байрлал + нормалийг нэг буферт (stride 24 байт). */
  function meshBuffer(m, w, on) {
    const lim = Math.cos(SMOOTH_ANGLE * DEG);
    const out = new Float32Array(m.n * 18);
    for (let f = 0; f < m.n; f++) {
      const fx = m.fnorm[f * 3], fy = m.fnorm[f * 3 + 1], fz = m.fnorm[f * 3 + 2];
      for (let k = 0; k < 3; k++) {
        let nx = fx, ny = fy, nz = fz;
        if (on) {
          nx = ny = nz = 0;
          const v = w.vid[f * 3 + k];
          for (let i = w.off[v]; i < w.off[v + 1]; i++) {
            const g = w.adj[i];
            const gx = m.fnorm[g * 3], gy = m.fnorm[g * 3 + 1], gz = m.fnorm[g * 3 + 2];
            if (fx * gx + fy * gy + fz * gz >= lim) { nx += gx; ny += gy; nz += gz; }
          }
          const len = Math.hypot(nx, ny, nz);
          if (len < 1e-9) { nx = fx; ny = fy; nz = fz; } else { nx /= len; ny /= len; nz /= len; }
        }
        const o = f * 18 + k * 6, p = f * 9 + k * 3;
        out[o] = m.pos[p]; out[o + 1] = m.pos[p + 1]; out[o + 2] = m.pos[p + 2];
        out[o + 3] = nx; out[o + 4] = ny; out[o + 5] = nz;
      }
    }
    return out;
  }

  /* ОНЦЛОХ ирмэгүүд, шугамын буферын хэлбэрээр (stride 28 байт).
   *
   * Гурвалжны бүх ирмэгийг зурвал 27 мянган нүүртэй тохой бол хар толбо болно —
   * харагдах зүйлгүй. Тиймээс зөвхөн хоёр талын өнцөг нь гөлгөрүүлэлтийн
   * босгыг давсан (өөрөөр хэлбэл гөлгөрөөгүй үлдсэн) ирмэг, мөн зөвхөн нэг
   * талтай ирмэгийг үлдээнэ. Энэ нь яг эд ангийн жинхэнэ ирмэгүүд — AutoCAD-ын
   * далд шугам арилгасан харагдацтай ижил уншигдана. */
  const EKEY = 8388608;

  function edgeBuffer(m, w) {
    const edges = new Map();                     // түлхүүр -> [тал1, тал2]
    for (let f = 0; f < m.n; f++) {
      for (let k = 0; k < 3; k++) {
        const a = w.vid[f * 3 + k], b = w.vid[f * 3 + ((k + 1) % 3)];
        if (a === b) continue;
        const key = a < b ? a * EKEY + b : b * EKEY + a;
        const hit = edges.get(key);
        if (hit === undefined) edges.set(key, [f, -1]);
        else if (hit[1] < 0) hit[1] = f;
      }
    }
    const lim = Math.cos(SMOOTH_ANGLE * DEG);
    const out = [];
    const push = (v) => {
      out.push(w.vpos[v * 3], w.vpos[v * 3 + 1], w.vpos[v * 3 + 2],
               WIRE_COL[0], WIRE_COL[1], WIRE_COL[2], WIRE_COL[3]);
    };
    edges.forEach((fs, key) => {
      const f = fs[0], g = fs[1];
      const keep = g < 0 || (m.fnorm[f * 3] * m.fnorm[g * 3] +
        m.fnorm[f * 3 + 1] * m.fnorm[g * 3 + 1] +
        m.fnorm[f * 3 + 2] * m.fnorm[g * 3 + 2]) < lim;
      if (keep) { push(Math.floor(key / EKEY)); push(key % EKEY); }
    });
    return new Float32Array(out);
  }

  // ------------------------------------------------------------------
  // Тор
  // ------------------------------------------------------------------

  function makeQuad() {
    bufQuad = upload(bufQuad, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]));
  }

  /* Торны алхам: харагдацын зайд тааруулан 10-ын зэрэг сонгоно. Нарийн
   * давхарга нь ойртох тусам бүдгэрч дараагийн зэрэг рүү жигд шилжинэ. */
  function gridStep() {
    const L = Math.log10(Math.max(cam.dist, 1e-3) * 0.3);
    const base = Math.pow(10, Math.floor(L));
    return { base, t: L - Math.floor(L) };
  }

  // ------------------------------------------------------------------
  // Зурах
  // ------------------------------------------------------------------

  function resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const w = Math.max(1, Math.round(canvas.clientWidth * dpr));
    const h = Math.max(1, Math.round(canvas.clientHeight * dpr));
    if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }
  }

  function draw() {
    resize();
    const w = canvas.width, h = canvas.height, aspect = w / h;
    const size = model ? model.size : 200;
    const far = cam.dist * 12 + size * 12 + 1000;
    if (cam.ortho) {
      orthographic(mProj, 2 * cam.dist * Math.tan(FOV / 2), aspect,
        -(cam.dist * 6 + size * 6), far);
    } else {
      perspective(mProj, FOV, aspect, Math.max(cam.dist * 0.004, size * 0.002, 0.01), far);
    }
    basis = viewMatrix(mView, cam.az, cam.el, cam.dist, cam.target);

    const bg = shading === 'material' ? MAT_BG : VIEW_BG;
    gl.viewport(0, 0, w, h);
    gl.clearColor(bg[0], bg[1], bg[2], 1);
    gl.enable(gl.DEPTH_TEST);
    gl.depthMask(true);
    gl.disable(gl.BLEND);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);

    if (model) {
      const wire = shading === 'wire';
      gl.useProgram(progMesh.p);
      gl.uniformMatrix4fv(progMesh.u.uProj, false, mProj);
      gl.uniformMatrix4fv(progMesh.u.uView, false, mView);
      gl.uniform3fv(progMesh.u.uAlbedo, wire ? VIEW_BG
        : (shading === 'material' ? OBJ_STEEL : OBJ_GRAY));
      gl.uniform1f(progMesh.u.uMetal, shading === 'material' ? 1 : 0);
      gl.uniform1f(progMesh.u.uFlat, wire ? 1 : 0);
      // Ирмэг нь гадаргуутайгаа яг ижил гүнд байдаг тул дүүргэлтийг бага
      // зэрэг ухраана — эс тэгвээс шугамууд толботож алга болно.
      gl.enable(gl.POLYGON_OFFSET_FILL);
      gl.polygonOffset(1, 1);
      gl.bindBuffer(gl.ARRAY_BUFFER, bufMesh);
      gl.enableVertexAttribArray(progMesh.a.aPos);
      gl.vertexAttribPointer(progMesh.a.aPos, 3, gl.FLOAT, false, 24, 0);
      gl.enableVertexAttribArray(progMesh.a.aNrm);
      gl.vertexAttribPointer(progMesh.a.aNrm, 3, gl.FLOAT, false, 24, 12);
      gl.drawArrays(gl.TRIANGLES, 0, model.tris * 3);
      gl.disable(gl.POLYGON_OFFSET_FILL);
      gl.disableVertexAttribArray(progMesh.a.aNrm);

      if (wire || wireOverlay) {
        gl.enable(gl.BLEND);
        gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
        gl.useProgram(progLine.p);
        gl.uniformMatrix4fv(progLine.u.uProj, false, mProj);
        gl.uniformMatrix4fv(progLine.u.uView, false, mView);
        gl.uniform1f(progLine.u.uAlpha, wire ? 0.95 : 0.30);
        gl.bindBuffer(gl.ARRAY_BUFFER, bufEdge);
        gl.enableVertexAttribArray(progLine.a.aPos);
        gl.vertexAttribPointer(progLine.a.aPos, 3, gl.FLOAT, false, 28, 0);
        gl.enableVertexAttribArray(progLine.a.aCol);
        gl.vertexAttribPointer(progLine.a.aCol, 4, gl.FLOAT, false, 28, 12);
        gl.drawArrays(gl.LINES, 0, nEdgeVerts);
        gl.disableVertexAttribArray(progLine.a.aCol);
        gl.disable(gl.BLEND);
      }
    }

    // Тор нь мешийн ДАРАА зурагдана: гүний шалгуур асаалттай тул биетийн ард
    // нуугдана, харин гүн рүү бичихгүй тул өөрөө өөрийгөө хачирлахгүй.
    // Тэнхлэгийн түвшнээс харахад шал нь ганц шугам болдог тул нуухад цэвэр.
    if (Math.abs(cam.el) > 3 * DEG) drawGrid(h);

    drawGizmo();
  }

  function drawGrid(pixH) {
    const { base, t } = gridStep();
    const extent = cam.dist * 5;
    // Дөрвөлжингийн төвийг бүдүүн алхамд оруулна: ингэснээр хээний фаз нь
    // дэлхийн эх цэгтэй тааран, камер зөөгдөхөд тор "гулсахгүй".
    const grid10 = base * 10;
    const ox = Math.round(cam.target[0] / grid10) * grid10;
    const oy = Math.round(cam.target[1] / grid10) * grid10;
    // Нэг пикселийн дэлхийн хэмжээ: перспективт гүнд пропорциональ.
    const px = cam.ortho
      ? (2 * cam.dist * Math.tan(FOV / 2)) / pixH
      : (2 * Math.tan(FOV / 2)) / pixH;

    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
    gl.depthMask(false);
    gl.useProgram(progGrid.p);
    gl.uniformMatrix4fv(progGrid.u.uProj, false, mProj);
    gl.uniformMatrix4fv(progGrid.u.uView, false, mView);
    gl.uniform2f(progGrid.u.uOrigin, ox, oy);
    gl.uniform1f(progGrid.u.uExtent, extent);
    gl.uniform1f(progGrid.u.uStep, base);
    gl.uniform1f(progGrid.u.uFine, 1 - t);
    gl.uniform1f(progGrid.u.uPx, px);
    gl.uniform1f(progGrid.u.uPersp, cam.ortho ? 0 : 1);
    gl.uniform2f(progGrid.u.uAxis, -ox, -oy);
    gl.uniform2f(progGrid.u.uCenter, cam.target[0] - ox, cam.target[1] - oy);
    gl.uniform2f(progGrid.u.uFade, cam.dist * 1.6, cam.dist * 3.6);
    gl.bindBuffer(gl.ARRAY_BUFFER, bufQuad);
    gl.enableVertexAttribArray(progGrid.a.aPos);
    gl.vertexAttribPointer(progGrid.a.aPos, 2, gl.FLOAT, false, 0, 0);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    gl.depthMask(true);
    gl.disable(gl.BLEND);
  }

  function loop() {
    if (anim) stepAnim();
    if (dirty) { dirty = false; draw(); }
    requestAnimationFrame(loop);
  }

  // ------------------------------------------------------------------
  // Тэнхлэгийн gizmo (жижиг 2D зурагт)
  // ------------------------------------------------------------------

  const GIZMO_AXES = [
    { v: [1, 0, 0], c: '#e0566a', n: 'X', view: 'right' },
    { v: [0, 1, 0], c: '#8ecb2f', n: 'Y', view: 'back' },
    { v: [0, 0, 1], c: '#4a8fdd', n: 'Z', view: 'top' },
    { v: [-1, 0, 0], c: '#e0566a', n: 'X', view: 'left' },
    { v: [0, -1, 0], c: '#8ecb2f', n: 'Y', view: 'front' },
    { v: [0, 0, -1], c: '#4a8fdd', n: 'Z', view: 'bottom' },
  ];
  let gizmoHot = -1;

  function gizmoPoints() {
    const g = dom.gizmo, R = g.width / 2 - 13, cx = g.width / 2, cy = g.height / 2;
    return GIZMO_AXES.map((a, i) => ({
      i, a, pos: i < 3,
      x: cx + (basis[0][0] * a.v[0] + basis[0][1] * a.v[1] + basis[0][2] * a.v[2]) * R,
      y: cy - (basis[1][0] * a.v[0] + basis[1][1] * a.v[1] + basis[1][2] * a.v[2]) * R,
      z: basis[2][0] * a.v[0] + basis[2][1] * a.v[1] + basis[2][2] * a.v[2],
    }));
  }

  function drawGizmo() {
    const g = dom.gizmo;
    if (!g) return;
    const ctx = g.getContext('2d');
    ctx.clearRect(0, 0, g.width, g.height);
    const cx = g.width / 2, cy = g.height / 2;
    gizmoPoints().sort((p, q) => p.z - q.z).forEach((p) => {
      if (p.pos) {
        ctx.strokeStyle = p.a.c; ctx.globalAlpha = 0.85; ctx.lineWidth = 2;
        ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(p.x, p.y); ctx.stroke();
      }
      ctx.globalAlpha = 1;
      const hot = gizmoHot === p.i;
      ctx.beginPath(); ctx.arc(p.x, p.y, 9.5, 0, Math.PI * 2);
      if (p.pos || hot) {
        ctx.fillStyle = p.a.c; ctx.fill();
      } else {
        ctx.fillStyle = 'rgba(30,30,30,.55)'; ctx.fill();
        ctx.strokeStyle = p.a.c; ctx.lineWidth = 2; ctx.stroke();
      }
      if (p.pos || hot) {
        ctx.fillStyle = '#15181d';
        ctx.font = '600 11px "Segoe UI", sans-serif';
        ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        ctx.fillText((p.pos ? '' : '-') + p.a.n, p.x, p.y + 0.5);
      }
    });
  }

  // ------------------------------------------------------------------
  // Камерын үйлдэл
  // ------------------------------------------------------------------

  const norm = (a) => Math.atan2(Math.sin(a), Math.cos(a));

  function goTo(to, instant) {
    if (to.ortho !== undefined) cam.ortho = to.ortho;
    if (instant) {
      if (to.az !== undefined) cam.az = to.az;
      if (to.el !== undefined) cam.el = to.el;
      if (to.dist !== undefined) cam.dist = to.dist;
      if (to.target) cam.target = to.target.slice();
      anim = null;
      updateHud();
      requestRender();
      return;
    }
    anim = {
      t0: performance.now(), ms: 220,
      from: { az: cam.az, el: cam.el, dist: cam.dist, target: cam.target.slice() },
      daz: norm((to.az === undefined ? cam.az : to.az) - cam.az),
      el: to.el === undefined ? cam.el : to.el,
      dist: to.dist === undefined ? cam.dist : to.dist,
      target: to.target ? to.target.slice() : cam.target.slice(),
    };
  }

  function stepAnim() {
    const k = Math.min(1, (performance.now() - anim.t0) / anim.ms);
    const e = k * k * (3 - 2 * k);
    cam.az = anim.from.az + anim.daz * e;
    cam.el = anim.from.el + (anim.el - anim.from.el) * e;
    cam.dist = anim.from.dist + (anim.dist - anim.from.dist) * e;
    for (let i = 0; i < 3; i++) {
      cam.target[i] = anim.from.target[i] + (anim.target[i] - anim.from.target[i]) * e;
    }
    if (k >= 1) anim = null;
    dirty = true;
    updateHud();
  }

  function setView(name, instant) {
    const v = AXIS_VIEWS[name];
    if (v) goTo({ az: v[0] * DEG, el: v[1] * DEG, ortho: true }, instant);
  }

  function frameAll(instant) {
    const lo = model ? model.lo : [-100, -100, -100];
    const hi = model ? model.hi : [100, 100, 100];
    const c = [0, 1, 2].map((i) => (lo[i] + hi[i]) / 2);
    const r = Math.max(Math.hypot(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]) / 2, 1);
    goTo({ target: c, dist: (r / Math.sin(FOV / 2)) * 1.05 }, instant);
  }

  function nearestAcadView() {
    const d = [
      -Math.cos(cam.el) * Math.sin(cam.az),
      -Math.cos(cam.el) * Math.cos(cam.az),
      Math.sin(cam.el),
    ];
    let best = ACAD_VIEWS[0], score = -Infinity;
    ACAD_VIEWS.forEach((v) => {
      const L = Math.hypot(v.dir[0], v.dir[1], v.dir[2]);
      const s = (v.dir[0] * d[0] + v.dir[1] * d[1] + v.dir[2] * d[2]) / L;
      if (s > score) { score = s; best = v; }
    });
    return best.key;
  }

  // ------------------------------------------------------------------
  // HUD
  // ------------------------------------------------------------------

  function detectView() {
    const el = cam.el / DEG, az = norm(cam.az) / DEG;
    for (const k in AXIS_VIEWS) {
      const [a, e] = AXIS_VIEWS[k];
      if (Math.abs(el - e) > 0.6) continue;
      if (Math.abs(e) > 89) return k;                       // дээр/доороос — азимут хамаагүй
      if (Math.abs(norm((az - a) * DEG) / DEG) < 0.6) return k;
    }
    return 'user';
  }

  function fmt(v) {
    const a = Math.abs(v);
    return (a >= 1000 ? v.toFixed(0) : a >= 10 ? v.toFixed(1) : v.toFixed(2)) + ' мм';
  }

  function stepText() {
    const { base } = gridStep();
    return base >= 1 ? base.toFixed(0) + ' мм' : base.toFixed(2) + ' мм';
  }

  /* Камер хөдлөх бүрт — зөвхөн хөнгөн бичиглэлүүд. */
  function updateHud() {
    cam.view = detectView();
    if (dom.corner) {
      dom.corner.innerHTML = '<b>' + VIEW_MN[cam.view] +
        (cam.ortho ? ' · ортогональ' : ' · перспектив') + '</b><span>' +
        (model ? model.name : 'эд анги сонгоогүй') + '</span>';
    }
    if (dom.stats) {
      dom.stats.innerHTML = (model
        ? 'Гурвалжин ' + model.tris.toLocaleString('en-US') + ' · Орой ' +
          model.verts.toLocaleString('en-US') + '<br>'
        : '') + 'Тор ' + stepText();
    }
  }

  /* Меш солигдох, гөлгөрүүлэлт өөрчлөгдөх үед — хажуугийн самбар. */
  function updatePanel() {
    if (!dom.npanel) return;
    if (!model) {
      dom.npanel.innerHTML = '<div class="np-head">Зүйл</div>' +
        '<div class="np-empty">Эд анги сонгоно уу</div>';
      return;
    }
    const d = [0, 1, 2].map((i) => model.hi[i] - model.lo[i]);
    const c = [0, 1, 2].map((i) => (model.hi[i] + model.lo[i]) / 2);
    const row = (k, v) => '<div class="np-row"><span>' + k + '</span><i>' + v + '</i></div>';
    dom.npanel.innerHTML =
      '<div class="np-head">Зүйл</div>' +
      '<div class="np-name">' + model.name + '</div>' +
      '<div class="np-title">Хэмжээ</div>' +
      ['X', 'Y', 'Z'].map((ax, i) => row(ax, fmt(d[i]))).join('') +
      '<div class="np-title">Байрлал (төв)</div>' +
      ['X', 'Y', 'Z'].map((ax, i) => row(ax, fmt(c[i]))).join('') +
      '<div class="np-title">Меш</div>' +
      row('Гурвалжин', model.tris.toLocaleString('en-US')) +
      row('Орой', model.verts.toLocaleString('en-US')) +
      row('Гөлгөрүүлэлт', smooth ? SMOOTH_ANGLE + '°' : 'хавтгай');
  }

  // ------------------------------------------------------------------
  // Оролт
  // ------------------------------------------------------------------

  function pixelScale() {
    return (2 * cam.dist * Math.tan(FOV / 2)) / Math.max(canvas.clientHeight, 1);
  }

  function bindInput() {
    let drag = null;

    canvas.addEventListener('contextmenu', (e) => e.preventDefault());
    canvas.addEventListener('pointerdown', (e) => {
      canvas.setPointerCapture(e.pointerId);
      // Blender: дунд товч тойруулж, Shift+дунд зөөнө. Дунд товчгүй хулганад
      // зүүн товч тойруулж, Shift эсвэл баруун товч зөөнө.
      drag = { x: e.clientX, y: e.clientY, pan: e.shiftKey || e.button === 2 };
      anim = null;
      e.preventDefault();
    });
    canvas.addEventListener('pointermove', (e) => {
      if (!drag) return;
      const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
      drag.x = e.clientX; drag.y = e.clientY;
      if (drag.pan) {
        const k = pixelScale();
        for (let i = 0; i < 3; i++) {
          cam.target[i] += -basis[0][i] * dx * k + basis[1][i] * dy * k;
        }
      } else {
        cam.az = norm(cam.az + dx * 0.007);
        cam.el = Math.max(-89.9 * DEG, Math.min(89.9 * DEG, cam.el + dy * 0.007));
      }
      updateHud();
      requestRender();
    });
    const stop = () => { drag = null; };
    canvas.addEventListener('pointerup', stop);
    canvas.addEventListener('pointercancel', stop);

    canvas.addEventListener('wheel', (e) => {
      e.preventDefault();
      cam.dist = Math.max(0.01, Math.min(1e7,
        cam.dist * Math.exp((e.deltaY > 0 ? 1 : -1) * 0.16)));
      updateHud();
      requestRender();
    }, { passive: false });

    root.addEventListener('pointerenter', () => { hovering = true; });
    root.addEventListener('pointerleave', () => { hovering = false; });

    const g = dom.gizmo;
    g.addEventListener('pointermove', (e) => {
      const r = g.getBoundingClientRect();
      const mx = (e.clientX - r.left) * (g.width / r.width);
      const my = (e.clientY - r.top) * (g.height / r.height);
      let hot = -1;
      gizmoPoints().forEach((p) => { if (Math.hypot(p.x - mx, p.y - my) < 11) hot = p.i; });
      if (hot !== gizmoHot) { gizmoHot = hot; requestRender(); }
    });
    g.addEventListener('pointerleave', () => {
      if (gizmoHot !== -1) { gizmoHot = -1; requestRender(); }
    });
    g.addEventListener('pointerdown', (e) => {
      e.stopPropagation();
      if (gizmoHot >= 0) setView(GIZMO_AXES[gizmoHot].view);
    });

    // Товчлолууд нь Blender шиг ХУЛГАНА дээр нь байх үед л ажиллана —
    // зүүн талын формд тоо бичиж байхад харагдац үсрэхгүй.
    window.addEventListener('keydown', (e) => {
      const t = document.activeElement;
      if (t && /^(INPUT|SELECT|TEXTAREA)$/.test(t.tagName)) return;
      if (e.key === 'F12') { e.preventDefault(); doRender(); return; }
      if (!hovering) return;
      const num = e.code.startsWith('Numpad') ? e.code.slice(6) : e.key;
      const plain = { 1: 'front', 3: 'right', 7: 'top', 9: 'bottom' };
      const ctrl = { 1: 'back', 3: 'left', 7: 'bottom' };
      if (plain[num]) {
        setView((e.ctrlKey && ctrl[num]) || plain[num]);
      } else if (num === '5') {
        cam.ortho = !cam.ortho; updateHud(); requestRender();
      } else if (num === '.' || num === 'Decimal' || e.code === 'Home') {
        frameAll();
      } else if (e.code === 'KeyZ') {
        setShading(e.shiftKey ? (shading === 'wire' ? 'solid' : 'wire')
          : (shading === 'solid' ? 'material' : 'solid'));
      } else if (e.code === 'KeyN') {
        toggleNPanel();
      } else {
        return;
      }
      e.preventDefault();
    });

    new ResizeObserver(requestRender).observe(canvas);
  }

  // ------------------------------------------------------------------
  // Толгойн цэс ба товчнууд
  // ------------------------------------------------------------------

  function menuItems(which) {
    if (which === 'view') {
      return [
        { t: 'Бүгдийг багтаах', k: 'Home', f: () => frameAll() },
        { t: cam.ortho ? 'Перспектив' : 'Ортогональ', k: '5',
          f: () => { cam.ortho = !cam.ortho; updateHud(); requestRender(); } },
        { sep: 1 },
        { t: 'Урдаас', k: '1', f: () => setView('front') },
        { t: 'Араас', k: 'Ctrl 1', f: () => setView('back') },
        { t: 'Баруунаас', k: '3', f: () => setView('right') },
        { t: 'Зүүнээс', k: 'Ctrl 3', f: () => setView('left') },
        { t: 'Дээрээс', k: '7', f: () => setView('top') },
        { t: 'Доороос', k: 'Ctrl 7', f: () => setView('bottom') },
        { sep: 1 },
        { t: 'AutoCAD-аар рендерлэх', k: 'F12', f: doRender },
      ];
    }
    return [
      { t: 'Гөлгөр сүүдэрлэх', k: smooth ? '✓' : '', f: () => setSmooth(true) },
      { t: 'Хавтгай сүүдэрлэх', k: smooth ? '' : '✓', f: () => setSmooth(false) },
      { sep: 1 },
      { t: 'Ирмэг харуулах', k: wireOverlay ? '✓' : '',
        f: () => { wireOverlay = !wireOverlay; requestRender(); } },
      { t: 'Хажуугийн самбар', k: 'N', f: toggleNPanel },
    ];
  }

  function openMenu(btn, which) {
    closeMenu();
    const box = document.createElement('div');
    box.className = 'vp-drop';
    menuItems(which).forEach((it) => {
      if (it.sep) { box.appendChild(document.createElement('hr')); return; }
      const b = document.createElement('button');
      b.innerHTML = '<span>' + it.t + '</span><i>' + (it.k || '') + '</i>';
      b.onclick = () => { closeMenu(); it.f(); };
      box.appendChild(b);
    });
    // Товчны байрлалыг .vp-body-тэй харьцуулж бодно: offsetLeft нь ямар эцэг
    // байрлалтай байхаас хамаарч өөр өөр гарна.
    const host = root.querySelector('.vp-body');
    box.style.left = Math.max(2, btn.getBoundingClientRect().left -
      host.getBoundingClientRect().left) + 'px';
    host.appendChild(box);
    dom.drop = box;
    setTimeout(() => document.addEventListener('pointerdown', closeMenu, { once: true }), 0);
  }

  function closeMenu() {
    if (dom.drop) { dom.drop.remove(); dom.drop = null; }
  }

  function setShading(mode) {
    shading = mode;
    root.querySelectorAll('[data-shade]').forEach((b) => {
      b.classList.toggle('on', b.dataset.shade === mode);
    });
    requestRender();
  }

  function setSmooth(on) {
    smooth = on;
    if (raw) {
      bufMesh = upload(bufMesh, meshBuffer(raw.m, raw.w, smooth));
      requestRender();
    }
    updatePanel();
  }

  function toggleNPanel() {
    npanelOn = !npanelOn;
    dom.npanel.classList.toggle('off', !npanelOn);
    requestRender();
  }

  function doRender() {
    if (!model) {
      toast('Эхлээд эд анги сонгоно уу');
      setTimeout(() => toast(''), 1600);
      return;
    }
    if (onRender) onRender(model.name, nearestAcadView());
  }

  function toast(text) {
    if (!dom.toast) return;
    dom.toast.textContent = text || '';
    dom.toast.classList.toggle('on', !!text);
  }

  // ------------------------------------------------------------------
  // Нийтийн API
  // ------------------------------------------------------------------

  function init(el, opts) {
    root = el;
    canvas = root.querySelector('canvas.vp-gl');
    dom = {
      gizmo: root.querySelector('canvas.vp-gizmo'),
      corner: root.querySelector('[data-el="corner"]'),
      stats: root.querySelector('[data-el="stats"]'),
      npanel: root.querySelector('[data-el="npanel"]'),
      toast: root.querySelector('[data-el="toast"]'),
    };
    onRender = (opts || {}).onRender || null;

    gl = canvas.getContext('webgl2', { antialias: true, alpha: false }) ||
         canvas.getContext('webgl', { antialias: true, alpha: false });
    if (!gl) { toast('Энэ хөтөч WebGL дэмжихгүй байна.'); return false; }

    progMesh = compile(MESH_VS, MESH_FS, ['aPos', 'aNrm']);
    progLine = compile(LINE_VS, LINE_FS, ['aPos', 'aCol']);
    progGrid = compile(GRID_VS, GRID_FS, ['aPos']);
    makeQuad();
    bindInput();

    root.querySelectorAll('[data-menu]').forEach((b) => {
      b.onclick = (e) => { e.stopPropagation(); openMenu(b, b.dataset.menu); };
    });
    root.querySelectorAll('[data-shade]').forEach((b) => {
      b.onclick = () => setShading(b.dataset.shade);
    });
    const rb = root.querySelector('[data-act="render"]');
    if (rb) rb.onclick = doRender;

    updateHud();
    updatePanel();
    requestAnimationFrame(loop);
    return true;
  }

  /* Нэрээр нь мешийг серверээс ачаална. Ижил эд ангийг дахин ачаалахад
   * камерыг хөдөлгөхгүй — дахин барьсны дараа өмнөх өнцөг хэвээр үлдэнэ. */
  async function load(name) {
    const same = model && model.name === name;
    toast('Мешийг AutoCAD-аас гаргаж байна…');
    try {
      const r = await fetch('/api/mesh?name=' + encodeURIComponent(name));
      if (!r.ok) {
        const j = await r.json().catch(() => ({}));
        throw new Error(j.error || 'сервер ' + r.status);
      }
      const head = (r.headers.get('X-Extents') || '').split(',').map(Number);
      const ext = head.length === 6 && head.every(isFinite) ? head : null;
      const buf = await r.arrayBuffer();

      const m = parseSTL(buf);
      place(m, ext);
      const w = weld(m);
      raw = { m, w };
      bufMesh = upload(bufMesh, meshBuffer(m, w, smooth));
      const edges = edgeBuffer(m, w);
      bufEdge = upload(bufEdge, edges);
      nEdgeVerts = edges.length / 7;
      model = {
        name, tris: m.n, verts: w.vpos.length / 3, lo: m.lo, hi: m.hi,
        size: Math.max(m.hi[0] - m.lo[0], m.hi[1] - m.lo[1], m.hi[2] - m.lo[2]),
      };
      toast('');
      if (same) { updateHud(); requestRender(); } else { frameAll(true); }
      updatePanel();
    } catch (err) {
      toast('меш гарсангүй: ' + err.message);
    }
  }

  return {
    init, load, toast, setView, setShading,
    frameAll: () => frameAll(),
    get shading() { return shading; },
  };
})();
