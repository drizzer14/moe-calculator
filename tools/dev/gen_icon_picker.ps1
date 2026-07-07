$icoDir = "C:\Users\DMYTRO~1\AppData\Local\Temp\claude\C--Users-Dmytro-Vasylkivskyi-14th-ua-moe-calculator\f2e9601c-85a3-404f-9c8f-dc5e269774a5\scratchpad\icons"
$out    = "C:\Users\DMYTRO~1\AppData\Local\Temp\claude\C--Users-Dmytro-Vasylkivskyi-14th-ua-moe-calculator\f2e9601c-85a3-404f-9c8f-dc5e269774a5\scratchpad\icon_picker.html"

# useful sets only: quest-type icons + the 3 generic MoE mark glyphs
$files = Get-ChildItem $icoDir -Filter *.png | Where-Object { $_.Name -like 'personal_missions_30__*' -or $_.Name -like 'library__marksOnGun__mark_*' }

function Categorize($short) {
  switch -Regex ($short) {
    'mark_\d|barrel_mark|master'                                   { 'Marks & mastery'; break }
    'damage|_hit|^.*fire|ram|kill_|hurt_|module_crit|save_hp'      { 'Damage & combat'; break }
    'assist|discover|meters'                                       { 'Assist & recon'; break }
    default                                                        { 'Progression & other' }
  }
}
# recommended-for hints for our three data points
$rec = @{
  'icon_battle_condition_damage'      = 'DMG'
  'icon_battle_condition_improve'     = 'AVG'
  'mark_3'                            = '%'
  'icon_battle_condition_barrel_mark' = '%'
}
$catOrder = @('Marks & mastery','Damage & combat','Assist & recon','Progression & other')
$byCat = @{}
foreach ($c in $catOrder) { $byCat[$c] = @() }

foreach ($f in $files) {
  $imgPath = 'img://gui/maps/icons/' + ($f.Name -replace '__','/')       # -> img://gui/maps/icons/.../name.png
  $short   = ($f.BaseName -replace '.*__','')
  $label   = ($short -replace '^icon_battle_condition_','' -replace '_',' ')
  $b64     = [Convert]::ToBase64String([IO.File]::ReadAllBytes($f.FullName))
  $cat     = Categorize $short
  $tag     = if ($rec.ContainsKey($short)) { $rec[$short] } else { '' }
  $byCat[$cat] += [pscustomobject]@{ label=$label; short=$short; path=$imgPath; b64=$b64; tag=$tag }
}

$sb = [System.Text.StringBuilder]::new()
[void]$sb.AppendLine(@'
<style>
  :root{
    --bg:#e9e6df; --panel:#ffffff; --ink:#26241f; --muted:#6f6a5f;
    --line:#d8d2c6; --tile:#191b1d; --tile-line:#33373b;
    --gold:#c79a3f; --gold-soft:#e7c877; --green:#7fbf6a; --red:#d97a72;
    --shadow:0 1px 2px rgba(0,0,0,.06),0 8px 24px rgba(40,36,28,.08);
  }
  @media (prefers-color-scheme:dark){
    :root{ --bg:#17181a; --panel:#202225; --ink:#ece7db; --muted:#948d7e;
      --line:#30333733; --line:#313539; --tile:#0f1113; --tile-line:#2a2e32;
      --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 30px rgba(0,0,0,.35); }
  }
  :root[data-theme="light"]{ --bg:#e9e6df; --panel:#ffffff; --ink:#26241f; --muted:#6f6a5f;
    --line:#d8d2c6; --tile:#191b1d; --tile-line:#33373b;
    --shadow:0 1px 2px rgba(0,0,0,.06),0 8px 24px rgba(40,36,28,.08); }
  :root[data-theme="dark"]{ --bg:#17181a; --panel:#202225; --ink:#ece7db; --muted:#948d7e;
    --line:#313539; --tile:#0f1113; --tile-line:#2a2e32;
    --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 30px rgba(0,0,0,.35); }

  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);
    font-family:"Segoe UI",system-ui,-apple-system,sans-serif;line-height:1.5;
    -webkit-font-smoothing:antialiased}
  .wrap{max-width:1080px;margin:0 auto;padding:40px 28px 72px}
  header{border-bottom:1px solid var(--line);padding-bottom:22px;margin-bottom:26px}
  .eyebrow{font-size:12px;letter-spacing:.22em;text-transform:uppercase;color:var(--gold);
    font-weight:700;margin:0 0 8px}
  h1{font-size:30px;line-height:1.1;margin:0 0 12px;font-weight:800;letter-spacing:-.01em;
    text-wrap:balance}
  .lede{max-width:64ch;color:var(--muted);margin:0;font-size:15px}
  .lede b{color:var(--ink);font-weight:600}
  .tools{display:flex;gap:12px;align-items:center;margin:22px 0 4px;flex-wrap:wrap}
  #q{flex:1;min-width:220px;background:var(--panel);border:1px solid var(--line);
    color:var(--ink);border-radius:9px;padding:10px 13px;font-size:14px;font-family:inherit}
  #q:focus{outline:2px solid var(--gold);outline-offset:1px}
  .hint{font-size:12.5px;color:var(--muted)}
  h2{font-size:13px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);
    font-weight:700;margin:34px 0 14px;padding-bottom:7px;border-bottom:1px solid var(--line)}
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:14px}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:12px;
    padding:14px 12px 12px;box-shadow:var(--shadow);cursor:pointer;position:relative;
    transition:transform .12s ease,border-color .12s ease}
  .card:hover{transform:translateY(-2px);border-color:var(--gold)}
  .card:focus-visible{outline:2px solid var(--gold);outline-offset:2px}
  .tile{display:flex;align-items:center;justify-content:center;height:92px;border-radius:9px;
    background:radial-gradient(120% 120% at 50% 30%,#23262a 0%,var(--tile) 78%);
    border:1px solid var(--tile-line);margin-bottom:11px}
  .tile img{width:60px;height:60px;image-rendering:auto}
  .name{font-size:12.5px;font-weight:600;color:var(--ink);word-break:break-word;line-height:1.3}
  .path{font-family:"Cascadia Code",Consolas,monospace;font-size:10px;color:var(--muted);
    margin-top:5px;word-break:break-all;line-height:1.35}
  .tag{position:absolute;top:9px;right:9px;font-size:10px;font-weight:800;letter-spacing:.04em;
    padding:3px 7px;border-radius:20px;background:var(--gold);color:#1a160c}
  .copied{position:fixed;left:50%;bottom:26px;transform:translateX(-50%) translateY(20px);
    background:var(--gold);color:#1a160c;font-weight:700;font-size:13px;padding:10px 18px;
    border-radius:24px;box-shadow:0 8px 24px rgba(0,0,0,.3);opacity:0;pointer-events:none;
    transition:opacity .2s,transform .2s}
  .copied.show{opacity:1;transform:translateX(-50%) translateY(0)}
  .legend{display:flex;gap:16px;flex-wrap:wrap;margin-top:10px;font-size:12.5px;color:var(--muted)}
  .legend b{color:var(--gold)}
</style>
<div class="wrap">
  <header>
    <p class="eyebrow">MoE Calculator &middot; in-battle overlay</p>
    <h1>In-game icon picker</h1>
    <p class="lede">Every glyph below is real WoT client art (<b>128&times;128</b>), reachable from the
    widget by its <code>img://</code> path. Pick one for each readout row &mdash; <b>DMG</b>, <b>AVG</b>,
    <b>%</b> &mdash; and tell me the names, or drop your own 128&times;128 PNG into the slot later.
    I&rsquo;ve pre-tagged sensible defaults.</p>
    <div class="legend">Currently wired: <span><b>DMG</b> = damage</span><span><b>AVG</b> = improve</span><span><b>%</b> = mark 3</span></div>
    <div class="tools">
      <input id="q" type="text" placeholder="Filter by name (e.g. damage, assist, mark)&hellip;" autocomplete="off">
      <span class="hint">Click any card to copy its <code>img://</code> path.</span>
    </div>
  </header>
'@)

foreach ($cat in $catOrder) {
  $items = $byCat[$cat]
  if ($items.Count -eq 0) { continue }
  [void]$sb.AppendLine('  <h2>' + $cat + '</h2>')
  [void]$sb.AppendLine('  <div class="grid">')
  foreach ($it in $items) {
    $tagHtml = if ($it.tag) { '<span class="tag">' + $it.tag + '</span>' } else { '' }
    [void]$sb.AppendLine('    <div class="card" tabindex="0" data-path="' + $it.path + '" data-name="' + $it.short + '">' + $tagHtml +
      '<div class="tile"><img alt="' + $it.label + '" src="data:image/png;base64,' + $it.b64 + '"></div>' +
      '<div class="name">' + $it.label + '</div><div class="path">' + $it.path + '</div></div>')
  }
  [void]$sb.AppendLine('  </div>')
}

[void]$sb.AppendLine(@'
</div>
<div class="copied" id="toast">Copied path</div>
<script>
  const toast=document.getElementById('toast');
  function flash(t){toast.textContent=t;toast.classList.add('show');clearTimeout(flash._t);
    flash._t=setTimeout(()=>toast.classList.remove('show'),1400);}
  document.querySelectorAll('.card').forEach(c=>{
    const go=()=>{const p=c.dataset.path;
      if(navigator.clipboard){navigator.clipboard.writeText(p).then(()=>flash('Copied '+c.dataset.name)).catch(()=>flash(p));}
      else flash(p);};
    c.addEventListener('click',go);
    c.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();go();}});
  });
  const q=document.getElementById('q');
  q.addEventListener('input',()=>{const v=q.value.trim().toLowerCase();
    document.querySelectorAll('.card').forEach(c=>{
      c.style.display=(!v||c.dataset.name.toLowerCase().includes(v))?'':'none';});
    document.querySelectorAll('.grid').forEach(g=>{
      const any=[...g.children].some(c=>c.style.display!=='none');
      g.style.display=any?'':'none';g.previousElementSibling.style.display=any?'':'none';});
  });
</script>
'@)

[IO.File]::WriteAllText($out, $sb.ToString(), (New-Object System.Text.UTF8Encoding($false)))
Write-Output ("wrote {0} ({1:N0} bytes, {2} icons)" -f $out,(Get-Item $out).Length,$files.Count)