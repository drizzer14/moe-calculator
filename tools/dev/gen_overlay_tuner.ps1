$dir = "C:\Users\DMYTRO~1\AppData\Local\Temp\claude\C--Users-Dmytro-Vasylkivskyi-14th-ua-moe-calculator\f2e9601c-85a3-404f-9c8f-dc5e269774a5\scratchpad"
$ico = "$dir\icons"; $fdir = "$dir\fonts"
function B64($p){ [Convert]::ToBase64String([IO.File]::ReadAllBytes($p)) }
$bg   = B64 "$dir\bg_clean.jpg"
$mark = B64 "$ico\personal_missions_30__quest_type__128x128__icon_battle_condition_barrel_mark.png"
$imp  = B64 "$ico\personal_missions_30__quest_type__128x128__icon_battle_condition_improve.png"
$cnrg = B64 "$fdir\UniversCnRg.ttf"
$cnbd = B64 "$fdir\UniversCnBold.ttf"
# Real game font extracted from gui/flash/fontlib.swf (tools/dev/swf_font_to_ttf.py):
# the Flash efficiency-panel font -- $FieldFont=MoEBattle, $TitleFont=MoEBattle.
$znrg = B64 "$fdir\MoEBattle.ttf"
$znbd = B64 "$fdir\MoEBattle.ttf"

$tpl = @'
<style>
  /* Only the two Univers Condensed cuts from D:\Downloads\univers. weight<=500 -> Regular, >=600 -> Bold. */
  @font-face{font-family:"UniversCn";font-weight:400;font-style:normal;src:url(data:font/ttf;base64,__CNRG__) format("truetype")}
  @font-face{font-family:"UniversCn";font-weight:500;font-style:normal;src:url(data:font/ttf;base64,__CNRG__) format("truetype")}
  @font-face{font-family:"UniversCn";font-weight:600;font-style:normal;src:url(data:font/ttf;base64,__CNBD__) format("truetype")}
  @font-face{font-family:"UniversCn";font-weight:700;font-style:normal;src:url(data:font/ttf;base64,__CNBD__) format("truetype")}
  /* The REAL game font (from fontlib.swf). weight<=500 -> MoEBattle, >=600 -> MoEBattle. */
  /* Ship a SINGLE cut (MoEBattle 600 = the Bold glyphs); map every weight to it so the
     preview matches the mod (which bundles only MoEBattle.ttf). */
  @font-face{font-family:"MoEBattle";font-weight:400;font-style:normal;src:url(data:font/ttf;base64,__ZNBD__) format("truetype")}
  @font-face{font-family:"MoEBattle";font-weight:500;font-style:normal;src:url(data:font/ttf;base64,__ZNBD__) format("truetype")}
  @font-face{font-family:"MoEBattle";font-weight:600;font-style:normal;src:url(data:font/ttf;base64,__ZNBD__) format("truetype")}
  @font-face{font-family:"MoEBattle";font-weight:700;font-style:normal;src:url(data:font/ttf;base64,__ZNBD__) format("truetype")}
  :root{--bg:#14151a;--panel:#1d2027;--ink:#e9e6df;--muted:#8b93a1;--line:#2b2f38;--gold:#c79a3f}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);font-family:"Segoe UI",system-ui,sans-serif;display:flex;min-height:100vh}
  .stagewrap{flex:1;display:flex;align-items:flex-start;justify-content:center;padding:20px;overflow:auto}
  .stage{position:relative;width:1600px;height:900px;flex:none;border-radius:6px;overflow:hidden;
    background:#000 url("data:image/jpeg;base64,__BG__") center/cover no-repeat;box-shadow:0 10px 40px rgba(0,0,0,.5);outline:1px solid var(--line)}
  /* ---- overlay (mirrors MoEBattle.css; per-row gradient; MARGIN spacing -- flex gap is
         NOT supported in this Coherent build, verified against WG production CSS) ---- */
  /* z-index:0 makes root a stacking context so the ::after underlay's z-index:-1 stays scoped
     here (mirrors the mod, where position:fixed + z-index:9000 does the same) */
  #moe-battle-root{position:absolute;left:var(--left);top:var(--top);display:flex;flex-direction:column;
    font-family:var(--fam);z-index:0}
  .mb-row{position:relative;display:flex;flex-direction:row;align-items:center;white-space:nowrap;
    padding:var(--rpv) var(--rph);margin-bottom:var(--rowmb)}
  /* gradient on a masked ::before layer so the left soft-clip fades the BACKDROP only, not the numbers */
  .mb-row::before{content:"";position:absolute;left:0;top:0;right:0;bottom:0;background:var(--rowgrad);
    background-size:var(--rowbgsize,auto);background-position:var(--rowbgpos,0 0);opacity:var(--rowop,1);
    image-rendering:pixelated;-webkit-mask:var(--rowmask);mask:var(--rowmask)}
  /* optional dark radial UNDERLAY behind the checker (Dots mode): z-index:-1 keeps it below
     both the checker ::before and the numbers */
  .mb-row::after{content:"";position:absolute;left:0;top:0;right:0;bottom:0;z-index:-1;
    background:var(--uggrad,none);-webkit-mask:var(--ugmask,none);mask:var(--ugmask,none)}
  .mb-row>span{position:relative}
  /* icon = a transparent, positioned box: the GLYPH rides on ::after (painted on top) while the
     coloured GLOW is a background element on ::before behind it -- a radial gradient of the glow
     colour, replacing the old drop-shadow. */
  .mb-ico{display:block;flex:none;position:relative;width:var(--icosize);height:var(--icosize);
    margin-right:var(--icomr);transform:translate(var(--icotx,0),var(--icoty,0))}
  .mb-ico::before{content:"";position:absolute;left:50%;top:50%;z-index:-1;
    width:var(--icoglowsize);height:var(--icoglowsize);transform:translate(-50%,-50%);background:var(--icoglow)}
  .mb-ico::after{content:"";position:absolute;left:0;top:0;right:0;bottom:0;
    background-repeat:no-repeat;background-position:center;background-size:var(--icozoom);filter:var(--icofilter)}
  .mb-ico.dmg::after{background-image:url("data:image/png;base64,__MARK__")}
  .mb-ico.pct::after{background-image:url("data:image/png;base64,__IMP__")}
  .mb-sep,.mb-avg,.mb-delta{margin-left:var(--valml)}
  .mb-value{font-size:var(--valfs);font-weight:var(--valwt);letter-spacing:var(--valls);color:#fff;text-shadow:var(--numsh)}
  .mb-sep{font-size:var(--sepfs);font-weight:var(--sepwt);color:rgba(237,230,217,.45);text-shadow:var(--numsh)}
  .mb-delta{font-size:var(--deltafs);font-weight:var(--deltawt);color:#fff;text-shadow:var(--numsh)}
  /* Sign now = WHITE text + a colored GLOW (the dark legibility drop stays layered under it). */
  .mb-value.mb-up,.mb-delta.mb-up{color:#fff;text-shadow:var(--upsh)}
  .mb-value.mb-down,.mb-delta.mb-down{color:#fff;text-shadow:var(--downsh)}
  /* ---- panel ---- */
  .panel{width:360px;flex:none;background:var(--panel);border-left:1px solid var(--line);padding:18px 18px 50px;overflow:auto;height:100vh;position:sticky;top:0}
  .panel h1{font-size:16px;margin:0 0 4px;font-weight:800}
  .panel .sub{font-size:12px;color:var(--muted);margin:0 0 14px;line-height:1.5}
  .seg{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 14px}
  .seg button{flex:1;background:#14151a;border:1px solid var(--line);color:var(--ink);padding:6px 4px;border-radius:6px;font-size:12px;cursor:pointer}
  .seg button.on{border-color:var(--gold);color:var(--gold);font-weight:700}
  details{border:1px solid var(--line);border-radius:8px;margin-bottom:8px;background:#191b21}
  summary{padding:9px 12px;font-size:12.5px;font-weight:700;cursor:pointer;color:var(--gold);letter-spacing:.03em;text-transform:uppercase}
  .grp{padding:4px 12px 12px}
  .ctl{margin:8px 0}
  .ctl .lab{display:flex;justify-content:space-between;font-size:12px;margin-bottom:3px}
  .ctl .inp{display:flex;gap:8px;align-items:center}
  .ctl input[type=range]{flex:1;accent-color:var(--gold)}
  .ctl input[type=number]{width:64px;background:#0f1013;border:1px solid var(--line);color:var(--ink);border-radius:5px;padding:4px 6px;font-size:12px;font-variant-numeric:tabular-nums}
  .ctl input[type=color]{width:38px;height:26px;background:none;border:1px solid var(--line);border-radius:5px;padding:0;cursor:pointer}
  .row2{display:flex;gap:14px;align-items:center;margin:4px 0 12px;font-size:12.5px}
  .row2 label{display:flex;gap:6px;align-items:center;cursor:pointer}
  .out{background:#0f1013;border:1px solid var(--line);border-radius:8px;padding:11px;font-family:"Cascadia Code",Consolas,monospace;font-size:10.5px;color:#b9c2cf;white-space:pre;overflow-x:auto;line-height:1.5}
  .copy{margin-top:9px;width:100%;background:var(--gold);color:#1a160c;border:0;border-radius:8px;padding:10px;font-weight:800;font-size:13px;cursor:pointer}
  .note{font-size:10.5px;color:var(--muted);margin-top:12px;line-height:1.5}
  /* ---- 5-digit panel guide: translucent stand-in for WG's widened efficiency panel ---- */
  #panelGuide{position:absolute;z-index:5;display:none;border:2px dashed rgba(211,68,63,.9);
    background:linear-gradient(90deg,rgba(211,68,63,.04),rgba(211,68,63,.30));border-radius:2px;
    box-shadow:0 0 0 1px rgba(0,0,0,.45)}
  #panelGuide::after{content:"WG efficiency panel @ 5 digits";position:absolute;left:4px;top:-15px;
    font:700 10px "Segoe UI",system-ui,sans-serif;color:rgba(233,150,146,.98);white-space:nowrap;letter-spacing:.04em}
  /* ---- shift read-out: the logical-px value to paste into BATTLE_ANCHOR_X_SHIFT ---- */
  .shiftout{background:#0f1013;border:1px solid var(--gold);border-radius:8px;padding:9px 11px;margin-bottom:9px;
    font-family:"Cascadia Code",Consolas,monospace;font-size:11.5px;color:var(--gold);font-weight:700;
    font-variant-numeric:tabular-nums;line-height:1.4}
  /* ---- dither magnifier (only shown in Dots mode) ---- */
  #loupe{position:absolute;top:12px;right:12px;width:230px;background:rgba(10,11,14,.94);
    border:1px solid var(--line);border-radius:8px;padding:9px;font-family:"Segoe UI",system-ui,sans-serif;z-index:50}
  #loupe .loupelab{font-size:10px;letter-spacing:.08em;color:var(--gold);font-weight:700;margin-bottom:6px}
  #loupeSwatch{position:relative;height:120px;border-radius:5px;overflow:hidden;
    background:#20242c;background-image:linear-gradient(180deg,#2a2f38,#14161b)}
  #loupeDither{position:absolute;inset:0;image-rendering:pixelated;background-repeat:repeat}
  #loupeCap{font-size:10px;color:var(--muted);margin-top:6px;line-height:1.4}
</style>
<div class="stagewrap"><div class="stage" id="stage">
  <div id="moe-battle-root">
    <div class="mb-row"><span class="mb-ico dmg"></span><span class="mb-value mb-cd"></span><span class="mb-sep">/</span><span class="mb-value mb-avg">2,718</span></div>
    <div class="mb-row"><span class="mb-ico pct"></span><span class="mb-value mb-pct">84.73%</span><span class="mb-delta"></span></div>
  </div>
  <div id="panelGuide"></div>
  <div id="loupe"><div class="loupelab">DITHER MAGNIFIER</div><div id="loupeSwatch"><div id="loupeDither"></div></div><div id="loupeCap"></div></div>
</div></div>
<div class="panel">
  <h1>In-battle overlay &mdash; tuner v4</h1>
  <p class="sub">Real 4K frame @0.42&times;, real markup, calibrated 1&thinsp;rem&asymp;2.0&thinsp;px @3840 (measured off our live 13rem MoEBattle value). The backdrop is a fixed two-layer stack: a dark <b>background gradient</b> (with a left clip) under the <b>dots</b> dither (with its own fade) &mdash; both always on. Font toggle: <b>MoEBattle</b> is the actual game font (from <code>fontlib.swf</code>) vs the <b>Univers</b> lookalike. Sliders pair with number boxes; values drop into <code>MoEBattle.css</code>. <b>5-digit shift</b> (new): WG&rsquo;s efficiency panel widens a digit once a total passes 9999 &mdash; dial <b>Shift right</b> until the box clears the red panel guide; that logical-px number is <code>BATTLE_ANCHOR_X_SHIFT</code>.</p>
  <div class="seg" id="fontSeg"><button data-f="MoEBattle" class="on">MoEBattle (real game font)</button><button data-f="UniversCn">Univers (lookalike)</button></div>
  <div class="seg" id="caseSeg"><button data-c="above" class="on">DMG &gt; avg</button><button data-c="equal">= avg</button><button data-c="below">&lt; avg</button></div>
  <div class="row2"><label><input type="checkbox" id="cBounds"> show bounds</label><label><input type="checkbox" id="cWide" checked> 5-digit values</label><label><input type="checkbox" id="cGuide" checked> panel guide</label></div>
  <div id="controls"></div>
  <div class="shiftout" id="shiftOut"></div>
  <div class="out" id="out"></div>
  <button class="copy" id="copyBtn">Copy CSS values</button>
  <p class="note">Icon glow is a radial-gradient <b>background element</b> behind the glyph (<code>.mb-ico::before</code>) &mdash; verify it renders in Gameface before relying on it in-game. Icons are the real gold quest glyphs (WG&rsquo;s panel icons are green; swap art later).</p>
</div>
<script>
  var PXREM=2.0*(1600/3840), PXVW=16, PXVH=9;   // recalibrated off the REAL MoEBattle: 13rem value = 19px @3840 -> 2.0px/rem
  var SCALE=1600/3840;                          // stage shrink: 1 browser px on the stage == 1/SCALE game px @3840
  function rem(v){return (v*PXREM).toFixed(2)+"px";}
  // schema: [section,[ {id,label,min,max,step,val,unit} | {id,label,color,val} ]]
  var SCHEMA=[
    ["Position",[
      {id:"left",label:"Left (vw)",min:0,max:60,step:0.1,val:13.8},
      {id:"top",label:"Top (vh)",min:0,max:100,step:0.1,val:78.7}]],
    ["5-digit shift (efficiency panel widens past 9999)",[
      // shiftPx is in LOGICAL px -- the exact value that becomes constants.BATTLE_ANCHOR_X_SHIFT
      // (added to BATTLE_ANCHOR_X=264). 1 logical px == 1 rem == PXREM stage-px, so the overlay
      // moves by shiftPx*PXREM here. The guide is a translucent stand-in for WG's panel widened
      // by a digit: outline it over the backdrop, then raise Shift right until the box clears it.
      {id:"shiftPx",label:"Shift right - BATTLE_ANCHOR_X_SHIFT (logical px)",min:0,max:200,step:1,val:5},
      {id:"guideL",label:"Panel guide left (vw)",min:0,max:60,step:0.1,val:8.5},
      {id:"guideT",label:"Panel guide top (vh)",min:0,max:100,step:0.1,val:77.5},
      {id:"guideW",label:"Panel guide width (vw)",min:0,max:40,step:0.1,val:6.5},
      {id:"guideH",label:"Panel guide height (vh)",min:0,max:40,step:0.1,val:10}]],
    ["Typography",[
      {id:"valSize",label:"Number size (rem)",min:8,max:48,step:0.5,val:14},
      {id:"valWeight",label:"Number weight",min:300,max:700,step:100,val:600},
      {id:"valLS",label:"Letter-spacing (em)",min:-0.1,max:0.2,step:0.005,val:0},
      {id:"sepSize",label:"Separator size (rem)",min:6,max:40,step:0.5,val:14},
      {id:"sepWeight",label:"Separator weight",min:300,max:700,step:100,val:600},
      {id:"deltaSize",label:"Delta size (rem)",min:6,max:40,step:0.5,val:14},
      {id:"deltaWeight",label:"Delta weight",min:300,max:700,step:100,val:600}]],
    ["Layout",[
      {id:"rowGap",label:"Row gap / margin-bottom (rem)",min:-40,max:40,step:0.5,val:-11},
      {id:"icoGap",label:"Icon→text gap (rem)",min:-40,max:40,step:0.5,val:4},
      {id:"valGap",label:"Value gap (rem)",min:-30,max:30,step:0.5,val:4.5},
      {id:"rowPadV",label:"Row pad vert (rem)",min:0,max:30,step:0.5,val:8},
      {id:"rowPadH",label:"Row pad horiz (rem)",min:0,max:80,step:0.5,val:32}]],
    ["Icons",[
      {id:"icoSize",label:"Icon size (rem)",min:8,max:60,step:0.5,val:17},
      {id:"icoZoom",label:"Icon zoom (%)",min:100,max:500,step:1,val:260},
      {id:"icoPosX",label:"Icon nudge X (rem)",min:-30,max:30,step:0.5,val:0},
      {id:"icoPosY",label:"Icon nudge Y (rem)",min:-30,max:30,step:0.5,val:1},
      {id:"icoBright",label:"Icon brightness (x)",min:0.5,max:5,step:0.1,val:3},
      // Glow is now a background element behind the glyph (.mb-ico::before) painting a RADIAL
      // GRADIENT of the glow colour -- not a drop-shadow. Size = the glow box (rem); spread =
      // where the gradient fades to transparent (%); alpha = inner intensity.
      {id:"icoGlowSize",label:"Glow size (rem)",min:0,max:120,step:1,val:40},
      {id:"icoGlowSpread",label:"Glow spread (%)",min:0,max:100,step:1,val:60},
      {id:"icoGlowAlpha",label:"Glow alpha",min:0,max:1,step:0.01,val:0.9},
      {id:"icoGlowColor",label:"Glow colour",color:true,val:"#ffcd5a"}]],
    ["Dots (checker dither)",[
      // checker.png is a 2x2-cell tile at CELL game-px, tiled 1:1 (background-size:auto ->
      // native cells). The stage renders it at TRUE game scale (SCALE=1600/3840), so fine cells
      // go sub-pixel HERE -- read them in the magnified swatch (top-right). Cell size bakes into
      // checker.png via `gen_checker.py --cell N`. The dither is faded to a blob by its OWN
      // radial mask (fade shape size/centre + solid-to/gone-by below).
      {id:"cellPx",label:"Cell size (game px @3840)",min:1,max:8,step:1,val:2},
      {id:"loupeZoom",label:"Magnifier zoom (px / game-px)",min:1,max:10,step:1,val:5},
      {id:"dotAlpha",label:"Strength (opacity)",min:0,max:1,step:0.01,val:0.2},
      {id:"gradRX",label:"Fade shape size X (%)",min:0,max:250,step:1,val:223},
      {id:"gradRY",label:"Fade shape size Y (%)",min:0,max:250,step:1,val:120},
      {id:"gradCX",label:"Fade centre X (%)",min:0,max:100,step:1,val:32},
      {id:"gradCY",label:"Fade centre Y (%)",min:0,max:100,step:1,val:50},
      {id:"dotMaskIn",label:"Fade: solid to (%)",min:0,max:100,step:1,val:0},
      {id:"dotMaskOut",label:"Fade: gone by (%)",min:0,max:120,step:1,val:27}]],
    ["Background gradient (underlay)",[
      // The dark radial blob painted BEHIND the checker (::after, z-index:-1) -- the backdrop
      // that "worked before". Its own size/centre/alpha; its left edge fades via the clip below.
      {id:"ugRX",label:"Size X (%)",min:0,max:250,step:1,val:50},
      {id:"ugRY",label:"Size Y (%)",min:0,max:250,step:1,val:50},
      {id:"ugCX",label:"Centre X (%)",min:0,max:100,step:1,val:50},
      {id:"ugCY",label:"Centre Y (%)",min:0,max:100,step:1,val:48},
      {id:"ug1a",label:"Inner alpha",min:0,max:1,step:0.01,val:0.4},
      {id:"ug1p",label:"Inner pos (%)",min:0,max:100,step:1,val:0},
      {id:"ug2a",label:"Outer alpha",min:0,max:1,step:0.01,val:0},
      {id:"ug2p",label:"Outer pos (%)",min:0,max:100,step:1,val:58},
      {id:"clipStart",label:"Left clip start (%)",min:0,max:100,step:1,val:13},
      {id:"clipEnd",label:"Left clip end (%)",min:0,max:100,step:1,val:22}]],
    ["Number shadow",[
      {id:"shX",label:"Offset X (rem)",min:-10,max:10,step:0.5,val:0},
      {id:"shY",label:"Offset Y (rem)",min:-10,max:10,step:0.5,val:0},
      {id:"shBlur",label:"Blur (rem)",min:0,max:30,step:0.5,val:1},
      {id:"shAlpha",label:"Alpha",min:0,max:1,step:0.01,val:0.5},
      {id:"shColor",label:"Colour",color:true,val:"#000000"}]],
    ["Sign glow (up=green / down=red)",[
      // Sign is carried by a COLORED GLOW: numerals stay white, a green/red halo (two stacked
      // text-shadow passes) rides OVER the dark legibility drop above. Neutral = no glow.
      {id:"glowUp",label:"Up (above avg) glow colour",color:true,val:"#7BEC37"},
      {id:"glowDown",label:"Down (below avg) glow colour",color:true,val:"#D3443F"},
      {id:"glowB1",label:"Wide glow blur (rem)",min:0,max:40,step:0.5,val:6},
      {id:"glowA1",label:"Wide glow alpha",min:0,max:1,step:0.01,val:0.9},
      {id:"glowB2",label:"Tight core blur (rem)",min:0,max:40,step:0.5,val:1},
      {id:"glowA2",label:"Tight core alpha",min:0,max:1,step:0.01,val:0.9}]]
  ];
  var st={}, casev="above", famv="MoEBattle";
  SCHEMA.forEach(function(sec){sec[1].forEach(function(c){st[c.id]=c.val;});});
  st._wide=true; st._guide=true;   // 5-digit preview + panel guide on by default (see checkboxes)
  function hexA(hex,a){var n=parseInt(hex.slice(1),16);return "rgba("+((n>>16)&255)+","+((n>>8)&255)+","+(n&255)+","+a+")";}
  // Left-edge clip on the background-gradient underlay.
  function rowMask(){return (st.clipEnd<=st.clipStart)?"none":"linear-gradient(90deg,transparent "+st.clipStart+"%,#000 "+st.clipEnd+"%)";}
  // The dark radial UNDERLAY (::after) -- the pre-dots backdrop, its own size/centre/alpha.
  function ugGrad(){return "radial-gradient("+st.ugRX+"% "+st.ugRY+"% at "+st.ugCX+"% "+st.ugCY+"%,rgba(0,0,0,"+st.ug1a+") "+st.ug1p+"%,rgba(0,0,0,"+st.ug2a+") "+st.ug2p+"%)";}
  // Dots mode: ROUND dots laid out on a CHECKER (staggered) grid -- two radial-gradient dot
  // layers, the 2nd offset by half the pitch in x AND y so its dots fall in the 1st's gaps
  // (a checkerboard of dots). Faded to a soft blob by a radial MASK. u()=unit fn (px/rem).
  function remU(v){return v+"rem";}
  // WG's halftone is a CHECKER dither. Gameface does NOT tile a radial/conic-gradient via
  // background-size (renders one gradient), so we tile a small RASTER checker.png instead
  // (rasters DO tile -- proven by the garage progressbar). The real PNG is a 2x2-cell tile at
  // CELL game-px (background-size:auto -> native cells); here we generate the SAME tile in a
  // canvas so the cell-size slider previews live. opacity=strength; image-rendering:pixelated
  // keeps cells crisp; the radial MASK fades it to a blob. Cache by cell so we don't re-draw.
  var _ckCache={};
  function checkerURI(cell){
    if(_ckCache[cell])return _ckCache[cell];
    var n=cell*2,cv=document.createElement("canvas");cv.width=n;cv.height=n;
    var x=cv.getContext("2d");x.fillStyle="#000";
    for(var yy=0;yy<n;yy++)for(var xx=0;xx<n;xx++){
      if((((xx/cell)|0)+((yy/cell)|0))%2===0)x.fillRect(xx,yy,1,1);
    }
    return _ckCache[cell]=cv.toDataURL();
  }
  function ckBg(preview){return "url("+(preview?checkerURI(st.cellPx):"checker.png")+") repeat";}
  // The magnifier swatch: same tile, blown up to loupeZoom browser px per game px, at the set
  // opacity over a dark map-ish base -- the only honest way to READ a sub-pixel dither.
  function updateLoupe(){
    var tile=st.cellPx*2*st.loupeZoom,d=document.getElementById("loupeDither");
    d.style.backgroundImage="url("+checkerURI(st.cellPx)+")";
    d.style.backgroundSize=tile+"px "+tile+"px";
    d.style.opacity=st.dotAlpha;
    document.getElementById("loupeCap").textContent=
      st.loupeZoom+"× · "+st.cellPx+"px cells @3840 · opacity "+st.dotAlpha+
      " — stage shows this "+(st.loupeZoom/SCALE).toFixed(1)+"× smaller (true game scale)";
  }
  function dotMask(){return "radial-gradient("+st.gradRX+"% "+st.gradRY+"% at "+st.gradCX+"% "+st.gradCY+"%,#000 "+st.dotMaskIn+"%,transparent "+st.dotMaskOut+"%)";}
  function icoFilter(){return "brightness("+st.icoBright+")";}
  // Icon glow = a radial gradient painted on a background element (.mb-ico::before) behind the
  // glyph, in the glow colour. Replaces the old drop-shadow filter.
  function icoGlow(){return "radial-gradient(circle at 50% 50%,"+hexA(st.icoGlowColor,st.icoGlowAlpha)+" 0%,transparent "+st.icoGlowSpread+"%)";}
  function numSh(){return rem(st.shX)+" "+rem(st.shY)+" "+rem(st.shBlur)+" "+hexA(st.shColor,st.shAlpha);}
  // Sign glow = dark legibility drop (numSh) + two stacked colored passes at growing radius.
  function glowStack(hex){return "0px 0px "+rem(st.glowB1)+" "+hexA(hex,st.glowA1)+", 0px 0px "+rem(st.glowB2)+" "+hexA(hex,st.glowA2);}
  function signSh(hex){return numSh()+", "+glowStack(hex);}
  function apply(){
    var r=document.getElementById("moe-battle-root"),S=r.style;
    S.setProperty("--fam",'"'+famv+'","Arial Narrow",sans-serif');
    // --left = base anchor + the 5-digit shift (shiftPx is LOGICAL px == rem == PXREM stage-px).
    S.setProperty("--left",(st.left*PXVW + st.shiftPx*PXREM).toFixed(1)+"px");S.setProperty("--top",(st.top*PXVH).toFixed(1)+"px");
    S.setProperty("--rowmb",rem(st.rowGap));S.setProperty("--valml",rem(st.valGap));
    S.setProperty("--icomr",rem(st.icoGap));S.setProperty("--rpv",rem(st.rowPadV));S.setProperty("--rph",rem(st.rowPadH));
    // Backdrop = fixed two-layer stack: dots dither (::before) over background gradient (::after).
    var tile=(st.cellPx*2*SCALE).toFixed(3)+"px";
    S.setProperty("--rowgrad",ckBg(true));S.setProperty("--rowbgsize",tile+" "+tile);S.setProperty("--rowbgpos","0 0");S.setProperty("--rowop",st.dotAlpha);S.setProperty("--rowmask",dotMask());updateLoupe();
    S.setProperty("--uggrad",ugGrad());S.setProperty("--ugmask",rowMask());
    S.setProperty("--icosize",rem(st.icoSize));S.setProperty("--icozoom",st.icoZoom+"%");S.setProperty("--icofilter",icoFilter());
    S.setProperty("--icoglow",icoGlow());S.setProperty("--icoglowsize",rem(st.icoGlowSize));
    S.setProperty("--icotx",rem(st.icoPosX));S.setProperty("--icoty",rem(st.icoPosY));
    S.setProperty("--numsh",numSh());
    S.setProperty("--upsh",signSh(st.glowUp));S.setProperty("--downsh",signSh(st.glowDown));
    S.setProperty("--valfs",rem(st.valSize));S.setProperty("--valwt",st.valWeight);S.setProperty("--valls",st.valLS+"em");
    S.setProperty("--sepfs",rem(st.sepSize));S.setProperty("--sepwt",st.sepWeight);
    S.setProperty("--deltafs",rem(st.deltaSize));S.setProperty("--deltawt",st.deltaWeight);
    r.style.outline=st._bounds?"1px dashed #ff5":"none";
    var cd=document.querySelector(".mb-cd"),d=document.querySelector(".mb-delta");
    cd.className="mb-value mb-cd";d.className="mb-delta";
    var avg=document.querySelector(".mb-avg");
    if(casev==="above"){cd.classList.add("mb-up");cd.textContent="3,141";d.classList.add("mb-up");d.textContent="(+1.5%)";}
    else if(casev==="below"){cd.classList.add("mb-down");cd.textContent="2,100";d.classList.add("mb-down");d.textContent="(-1.2%)";}
    else{cd.textContent="2,718";d.textContent="(0%)";}
    // "5-digit values": preview the overlay's own numbers at 5 digits (the state that co-occurs
    // with WG's widened panel), so the box width you're clearing is realistic.
    if(st._wide){cd.textContent="1"+cd.textContent;avg.textContent="12,718";}else{avg.textContent="2,718";}
    // Panel guide = translucent stand-in for WG's widened efficiency panel.
    var gd=document.getElementById("panelGuide");
    gd.style.display=st._guide?"block":"none";
    gd.style.left=(st.guideL*PXVW).toFixed(1)+"px";gd.style.top=(st.guideT*PXVH).toFixed(1)+"px";
    gd.style.width=(st.guideW*PXVW).toFixed(1)+"px";gd.style.height=(st.guideH*PXVH).toFixed(1)+"px";
    document.getElementById("shiftOut").textContent=
      "BATTLE_ANCHOR_X_SHIFT = "+st.shiftPx+"   (logical px — anchor 264 → "+(264+st.shiftPx)+")";
    document.getElementById("out").textContent=cssOut();
  }
  function cssOut(){
    var glowGrad="radial-gradient(circle at 50% 50%, "+hexA(st.icoGlowColor,st.icoGlowAlpha)+" 0%, transparent "+st.icoGlowSpread+"%)";
    var sh=st.shX+"rem "+st.shY+"rem "+st.shBlur+"rem "+hexA(st.shColor,st.shAlpha);
    var famcss=(famv==="MoEBattle")?'"MoEBattle", "Arial Narrow", sans-serif':'"Univers Condensed", sans-serif';
    // ::before = dots dither (with its own radial fade mask). UNPREFIXED mask only -- WG's own
    // Gameface CSS uses `mask` and never `-webkit-mask`, so the copied CSS is deploy-ready.
    var beforeBody="  /* checker.png = "+st.cellPx+"px cells @3840 -- regen: python tools/dev/gen_checker.py --cell "+st.cellPx+" */\n  background: "+ckBg(false)+";\n  background-size: auto;\n  background-position: 0px 0px;\n  image-rendering: pixelated;\n  opacity: "+st.dotAlpha+";\n  mask: "+dotMask()+";\n";
    // ::after = background gradient underlay (z-index:-1 scoped by root's own z-index), left-clipped.
    var afterBlock=".mb-row::after {\n  content: \"\";\n  position: absolute; left: 0; top: 0; right: 0; bottom: 0;\n  z-index: -1;\n  background: "+ugGrad()+";\n"+((rowMask()!=="none")?("  mask: "+rowMask()+";\n"):"")+"}\n";
    return "/* MARGIN spacing -- flex gap is unsupported in Gameface */\n"+
      "#moe-battle-root {\n  left: "+st.left+"vw;\n  top: "+st.top+"vh;\n  font-family: "+famcss+";\n  padding: 0;\n}\n"+
      ".mb-row {\n  position: relative;\n  padding: "+st.rowPadV+"rem "+st.rowPadH+"rem;\n  margin-bottom: "+st.rowGap+"rem;\n}\n"+
      ".mb-row::before {\n  content: \"\";\n  position: absolute; left: 0; top: 0; right: 0; bottom: 0;\n"+beforeBody+"}\n"+
      afterBlock+
      ".mb-row > span { position: relative; }\n"+
      "/* Icon glow = a radial-gradient background element (::before) BEHIND the glyph, in the glow\n"+
      "   colour -- replaces the drop-shadow. The glyph rides on ::after so it paints on top; set its\n"+
      "   background-image per row (the mod sets it inline in MoEBattle.js). */\n"+
      ".mb-ico {\n  position: relative;\n  width: "+st.icoSize+"rem; height: "+st.icoSize+"rem;\n  margin-right: "+st.icoGap+"rem;\n  transform: translate("+st.icoPosX+"rem, "+st.icoPosY+"rem);\n}\n"+
      ".mb-ico::before {\n  content: \"\";\n  position: absolute; left: 50%; top: 50%; z-index: -1;\n  width: "+st.icoGlowSize+"rem; height: "+st.icoGlowSize+"rem;\n  transform: translate(-50%, -50%);\n  background: "+glowGrad+";\n}\n"+
      ".mb-ico::after {\n  content: \"\";\n  position: absolute; left: 0; top: 0; right: 0; bottom: 0;\n  background-repeat: no-repeat; background-position: center;\n  background-size: "+st.icoZoom+"%;\n  filter: brightness("+st.icoBright+");\n}\n"+
      ".mb-sep, .mb-value.mb-avg, .mb-delta { margin-left: "+st.valGap+"rem; }\n"+
      ".mb-value {\n  font-size: "+st.valSize+"rem; font-weight: "+st.valWeight+";\n  letter-spacing: "+st.valLS+"em;\n  text-shadow: "+sh+";\n}\n"+
      ".mb-sep { font-size: "+st.sepSize+"rem; font-weight: "+st.sepWeight+"; }\n"+
      ".mb-delta { font-size: "+st.deltaSize+"rem; font-weight: "+st.deltaWeight+"; text-shadow: "+sh+"; }\n"+
      "/* Sign = WHITE text + colored GLOW (dark drop kept underneath for legibility). */\n"+
      ".mb-value.mb-up,\n.mb-delta-num.mb-up {\n  color: #ffffff;\n  text-shadow: "+sh+",\n               0 0 "+st.glowB1+"rem "+hexA(st.glowUp,st.glowA1)+",\n               0 0 "+st.glowB2+"rem "+hexA(st.glowUp,st.glowA2)+";\n}\n"+
      ".mb-value.mb-down,\n.mb-delta-num.mb-down {\n  color: #ffffff;\n  text-shadow: "+sh+",\n               0 0 "+st.glowB1+"rem "+hexA(st.glowDown,st.glowA1)+",\n               0 0 "+st.glowB2+"rem "+hexA(st.glowDown,st.glowA2)+";\n}";
  }
  // build UI
  var host=document.getElementById("controls");
  SCHEMA.forEach(function(sec){
    var det=document.createElement("details");det.open=true;
    det.innerHTML="<summary>"+sec[0]+"</summary>";
    var g=document.createElement("div");g.className="grp";
    sec[1].forEach(function(c){
      var w=document.createElement("div");w.className="ctl";
      if(c.color){
        w.innerHTML="<div class='lab'><span>"+c.label+"</span></div><div class='inp'><input type='color' id='c_"+c.id+"'></div>";
        g.appendChild(w);var ci=w.querySelector("input");ci.value=st[c.id];
        ci.addEventListener("input",function(){st[c.id]=ci.value;apply();});
      }else{
        w.innerHTML="<div class='lab'><span>"+c.label+"</span></div><div class='inp'><input type='range' id='r_"+c.id+"' min='"+c.min+"' max='"+c.max+"' step='"+c.step+"'><input type='number' id='n_"+c.id+"' min='"+c.min+"' max='"+c.max+"' step='"+c.step+"'></div>";
        g.appendChild(w);
        var rg=w.querySelector("input[type=range]"),nu=w.querySelector("input[type=number]");
        rg.value=st[c.id];nu.value=st[c.id];
        function upd(v){v=parseFloat(v);if(isNaN(v))return;st[c.id]=v;rg.value=v;nu.value=v;apply();}
        rg.addEventListener("input",function(){upd(rg.value);});
        nu.addEventListener("input",function(){upd(nu.value);});
      }
    });
    det.appendChild(g);host.appendChild(det);
  });
  document.getElementById("cBounds").addEventListener("change",function(e){st._bounds=e.target.checked;apply();});
  document.getElementById("cWide").addEventListener("change",function(e){st._wide=e.target.checked;apply();});
  document.getElementById("cGuide").addEventListener("change",function(e){st._guide=e.target.checked;apply();});
  document.querySelectorAll("#fontSeg button").forEach(function(b){b.addEventListener("click",function(){famv=b.dataset.f;document.querySelectorAll("#fontSeg button").forEach(function(x){x.classList.remove("on");});b.classList.add("on");apply();});});
  document.querySelectorAll("#caseSeg button").forEach(function(b){b.addEventListener("click",function(){casev=b.dataset.c;document.querySelectorAll("#caseSeg button").forEach(function(x){x.classList.remove("on");});b.classList.add("on");apply();});});
  document.getElementById("copyBtn").addEventListener("click",function(){var t=cssOut();if(navigator.clipboard)navigator.clipboard.writeText(t);var b=document.getElementById("copyBtn");b.textContent="Copied ✓";setTimeout(function(){b.textContent="Copy CSS values";},1300);});
  apply();
</script>
'@

$tpl=$tpl.Replace('__BG__',$bg).Replace('__MARK__',$mark).Replace('__IMP__',$imp).Replace('__CNRG__',$cnrg).Replace('__CNBD__',$cnbd).Replace('__ZNRG__',$znrg).Replace('__ZNBD__',$znbd)
$out="$dir\overlay_preview.html"
[IO.File]::WriteAllText($out,$tpl,(New-Object System.Text.UTF8Encoding($false)))
Write-Output ("wrote {0} ({1:N0} bytes)" -f $out,(Get-Item $out).Length)