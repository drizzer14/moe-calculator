# 14th_ua's MoE Calculator — World of Tanks mod

Track your **Marks of Excellence (MoE)** progress for the vehicle you have selected,
in the Garage and live in battle. The mod reads the game's own MoE data and renders it
with the client's own mark art and interface styling, so it looks like a built-in part
of the interface rather than an add-on.

**English** · [Українська](#14th_uas-moe-calculator--українська)

|  |  |
|:--:|:--:|
| ![In-battle MoE overlay](assets/screenshots/battle.png) | ![Garage MoE bar](assets/screenshots/garage.png) |
| In-battle overlay | Garage MoE bar |
| ![Progress bar — Moving Average](assets/screenshots/progress_moving_average.png) | ![Progress bar — Damage Efficiency](assets/screenshots/progress_damage_efficiency.png) |
| Progress bar — Moving Average | Progress bar — Damage Efficiency |
| ![Garage MoE trend chart](assets/screenshots/trend.png) |  |
| Garage MoE trend chart |  |

## What it shows

### Garage MoE bar

A percentile bar in the vehicle-parameters panel with milestone ticks at **65% / 85% /
95%** — the 1 / 2 / 3-mark thresholds — each drawn with the client's own mark art. Every
tick is labelled with the combined damage that mark requires, and the bar fills to your
current standing. Above it, a readout shows your current average combined damage and your
current mark percentage for the selected vehicle.

**Ctrl+drag** the widget to move it anywhere on screen (hold **Shift** to lock the drag to
one axis). Where you drop it is remembered; the panel also has numeric position fields and a
**Follow Carousel Mode** option — see Settings.

Hovering the bar's mark tooltip also shows a weekly moving-average MoE trend chart —
per-battle dots on a fixed percentile axis, mark lines at 65% / 85% / 95% / 100%, day
dividers, and an end-of-day moving-average label for each day.

### In-battle overlay

A compact overlay over the HUD with two lines (an optional third row shows counted
assistance — see Settings):

- **Live combined damage vs your projected average** — the number is coloured by sign
  (red below your projection, white at it, green above).
- **Your projected MoE percentage** with the signed change versus where you started the
  battle.

### In-battle progress bar *(off by default)*

A wide bar in the **centre of the screen**, separate from the corner overlay, drawn either
**horizontally** (its original layout) or **vertically** beside the minimap — pick the
**Orientation** in Settings. By default it fades in when there is something new to show, holds
for a few seconds (five by default, adjustable in Settings), then fades out on its own, and
**holding Alt** also brings it up — independent of the overlay's own Alt-press setting; settings
below let you turn either trigger off, or pin the bar up permanently. The bar never takes mouse
input, and it stays hidden while the **Tab** scoreboard is open, while you are spectating, and
before you have a vehicle. Settings let you draw it **Large** and switch the fades off so it
appears and disappears instantly.

By default the bar sits at a **Fixed** built-in spot chosen by Orientation — centred above the
damage log when horizontal, beside the minimap when vertical. Switch **Alignment** to **Free**
in Settings to unlock it, then **Ctrl+drag** the bar to reposition it anywhere on screen — the
position is shared by both variants and remembered; the panel also has numeric X/Y fields for
it, greyed out while Alignment is Fixed — see Settings.

Turn it on in Settings and pick **one** of two bars — they are mutually exclusive:

- **Damage Efficiency** *(default)* — this battle's combined damage against all four
  requirements (**65% / 85% / 95% / 100%**) laid out on four equal quarters, with every
  requirement you have already passed lit up. No baseline needed, and it comes up on its own
  each time your damage this battle reaches a new high.
- **Moving Average** — where your career projected average combined damage sits between the
  mark you already hold and the next mark's requirement, with this battle's signed contribution
  beside it. The next-mark caption also carries an **ETA**: how many more battles you need at
  your current pace to reach it. It comes up whenever that projection moves. It needs a career
  baseline, so it shows nothing in replays, or after a relogin until you have visited the Garage.

You don't need to open Settings to switch bars mid-battle: press the **Mode Override Key**
(**K** by default, rebindable) to flip the current vehicle's bar between the two — the mod
remembers each vehicle's choice, and the bar reloads and reappears a few seconds after you
switch. An **Automatic Mode Toggle** can do the same on its own: once a vehicle's mark progress
reaches a percentage you set (before battle), its mode switches once, exactly as if you'd
pressed the key.

Three switches decide **when** it comes up: **Events** (a tracked battle event raises it, on by
default), **Alt Press** (holding Alt shows it, on by default) and **Always** (pins it on screen
permanently and greys out the other two, off by default). A separate **Transitions** switch
decides **how** it moves once it does — fading and sliding by default, or instant if you turn
it off — and how long it holds before fading away.

The corner overlay's position is fixed; the centre-screen bar's Fixed position follows
Orientation, or is fully draggable once you switch Alignment to Free — see *Layout* under
Settings. On a vehicle whose mark thresholds could not be fetched, neither bar draws — the
Garage bar still does.

## Compatibility

| Requirement | Detail |
|-------------|--------|
| **Game** | World of Tanks **EU 2.4.1.0** (Wargaming global client). Built for this version. |
| **Required** | **OpenWG GameFace** 1.2.2+ — install it first, or the widget will not appear. From [wgmods.net](https://wgmods.net) or [gitlab.com/openwg/wot.gameface](https://gitlab.com/openwg/wot.gameface). |

## Download & install

**Easiest — the one-click installer (Windows).** Download the latest
**`MoECalculator-Setup-<version>.exe`** from the
[**GitHub Releases**](https://github.com/drizzer14/moe-calculator/releases) page and run
it (close the game first). It finds your World of Tanks folder, installs the mod into
`mods\<version>\`, and adds its bundled dependencies — **OpenWG GameFace**,
**Aslain ModMenu**, and **ModsList** — for any you don't already have. On each
run it also checks GitHub and offers to fetch the newest
installer, so a copy you keep around stays current.

**Manual installation.** Grab `com.14th_ua.moe_calculator_<version>.wotmod` from the same
Releases page and follow **[`INSTALL.md`](./INSTALL.md)** — it covers the manual copy,
verifying it works, troubleshooting, and uninstalling.

## Settings

The mod adds a settings panel to the in-game **mod-settings menu**, provided by
**Aslain ModMenu (MSA)** — the standard settings host bundled with the installer. If MSA
isn't loaded, the mod still runs with both widgets on by default; you just won't see the panel.

The panel is grouped into named **categories**, each a bold header row followed by that
feature's controls — so a feature's own on/off switch is simply labelled **Enabled**. Column 1
holds the in-battle overlay plus everything Garage-related; column 2 holds the whole
centre-screen progress bar feature. Live preview images of both widgets sit in the panel and
update as you change the settings that affect their look:

| Setting | Default | What it does |
|---|---|---|
| *Battle Calculator* | — | Category header for the in-battle overlay. |
| **Enabled** | On | Shows the live MoE overlay during battle. |
| ↳ **Alt Press** | Off | Shows the overlay only while **Alt** is held; when off it is visible at all times. |
| ↳ **Counted Assistance Row** | On | Adds a third overlay row: the higher of tracking, spotting or stun assist, with an icon for whichever leads. |
| *Garage Widget* | — | Category header for the Garage bar. |
| **Enabled** | On | Shows the MoE percentile bar in the Garage, on the selected vehicle. |
| *Layout* (Garage) | — | Sub-category for the Garage widget's position. |
| **Follow Carousel Mode** | On | A pinned widget keeps shifting vertically with the vehicle carousel (single / double rows) so it never overlaps it. |
| **Horizontal (left X)** / **Vertical (top Y)** | 0 = auto | The pinned widget's distance from the left / top screen edge, in pixels. **Ctrl+drag** the widget to pin it (hold **Shift** to lock to one axis). |
| *Battle Progress* | — | Category header for the centre-screen progress bar — its own column, separate from the Battle Calculator. |
| **Enabled** | Off | Shows the centre-screen bar. Pick the mode and scale below, and when it comes up with the three switches beneath. |
| ↳ **Events** | On | Raises the bar on its own whenever a tracked battle event happens, then fades it away again. Ignored while **Always** is on. |
| ↳ **Alt Press** | On | Shows the bar only while **Alt** is held. Ignored while **Always** is on. |
| ↳ **Always** | Off | Keeps the bar on screen permanently; it never fades. Overrides both switches above, which grey out while this is on. |
| **Mode** | Damage Efficiency | The two mutually exclusive bars, **Damage Efficiency** *(default)* and **Moving Average** — an inline pair of radio buttons. |
| **Mode Override Key** | K | The in-battle key that flips the current vehicle's bar mode; the mod remembers each vehicle's own choice. |
| **Automatic Mode Toggle** | 100% (off) | Once a vehicle's mark progress reaches this percentage before battle, its mode switches once on its own — the same as pressing the override key. 100% disables it. |
| **Scale** | Default | **Default** or **Large**. Large draws a noticeably bigger bar — same layout, just larger. |
| **Moving Average: show %** | On | Shows your live Mark of Excellence percentage, with this battle counted, in brackets beside the current damage on the Moving Average bar. |
| **Moving Average: show change** | On | Shows how much this battle changes your moving average, as (+N), beside the current damage on the Moving Average bar. |
| **Damage Efficiency: show %** | On | Shows the Mark of Excellence percentage this battle's damage alone is worth, in brackets beside the current damage on the Damage Efficiency bar. |
| **Damage Efficiency: show change** | On | Shows the +N flash for the damage of your latest hit on the Damage Efficiency bar. |
| *Transitions* | — | Category header for how the centre-screen bar animates and how long it stays up. |
| **Enabled** | On | The bar fades and slides as it appears and disappears. Turn off to make it appear and disappear **instantly** instead; the bar still shows and still hides, only the motion is skipped. |
| ↳ **Events** | On | Animates the bar when a battle event brings it up (a damage tick) and lets it go again. |
| ↳ **Alt Press** | On | Animates the **Alt** peek. Off matches the game's own interface, which does not animate on Alt. |
| ↳ **Hold Duration (s)** | 5 | How many seconds the bar stays up before it starts fading away (or disappearing, if Transitions is off). Range 1–30. |
| *Layout* (Bar) | — | Category header for the centre-screen bar's orientation, anchor and position. |
| **Orientation** | Horizontal | **Horizontal** (the original layout) or **Vertical**, which draws it upright, sized to sit beside the minimap. |
| **Alignment** | Fixed | **Fixed** — the bar's built-in spot, chosen automatically by Orientation — or **Free**, an unanchored position you set by dragging or with the steppers below. |
| **Horizontal (left X)** / **Vertical (top Y)** | 0 = auto | The centre-screen bar's offset in pixels, shared by both bar modes. Greyed out unless **Alignment** is **Free** — **Ctrl+drag** the bar to set it once it is. |

Unchecking a master checkbox (**Battle Calculator**'s, **Battle Progress**'s, and
**Transitions**'s own **Enabled**) greys its indented children out; the Garage settings and the
bar's **Layout** category have no such master. **Always**, in turn, greys out **Events** and
**Alt Press** right above it once it's on. **Mode**, **Mode Override Key**, **Automatic Mode
Toggle**, **Scale**, **Orientation** and **Alignment** all sit alongside their category's master
rather than under it, so they stay clickable while the feature itself is off — they simply have
nothing to affect until you switch it on. The bar's position steppers (and dragging the bar)
grey out whenever **Alignment** is **Fixed**, since there is nothing to set while the bar sits
at its built-in spot. **0 / 0** is the default bottom-right position for the Garage widget, and
also the default (auto) position for the centre-screen progress bar under Free — both restored
by the panel's per-mod **Reset**. The Garage position settings apply to the Garage widget only;
the bar's **Layout** category applies to the centre-screen progress bar (shared by both modes) —
the corner overlay's position is fixed. What each progress-bar mode shows, and the career
baseline **Moving Average** needs, is described under *In-battle progress bar* above.

## Notes

- **After a game update**, move the `.wotmod` to the new `mods\<version>\` folder. A new
  client version may need a rebuilt mod — check the Releases page.

## MoE data source

The per-tank mark thresholds (the combined damage each mark needs) come from the **official
Wargaming API** — the real damage distribution, so the numbers are authoritative and current.
Thresholds are cached locally so switching vehicles is instant. The in-battle percentage between
marks is interpolated the same way Wargaming's own Marks of Excellence percentage is, for the
closest possible match to what the game itself would show you.

## Modpacks & license

Free to use, redistribute, and include in modpacks as long as it stays free and credits the
author (**14th_ua**) with a link back to this repository — see [`LICENSE.md`](./LICENSE.md).
For modpacks, add only the `.wotmod` and list OpenWG GameFace as a required dependency; don't
bundle GameFace yourself.

## Contributing / developers

Building, deploying, testing, and the repo layout are documented in
[`CLAUDE.md`](./CLAUDE.md) (and the dev loop in [`tools/dev/README.md`](./tools/dev/README.md)).

---

# 14th_ua's MoE Calculator — Українська

Відстежуйте прогрес **Знаків Класності** (Marks of Excellence) для обраної техніки — в
Ангарі та наживо в бою. Мод читає власні дані гри про класність і малює їх рідними іконками
та стилем інтерфейсу клієнта, тож він виглядає як вбудована частина інтерфейсу, а не
стороннє доповнення.

[English](#14th_uas-moe-calculator--world-of-tanks-mod) · **Українська**

|  |  |
|:--:|:--:|
| ![Смуга класності в Ангарі](assets/screenshots/garage.png) | ![Оверлей у бою](assets/screenshots/battle.png) |
| Смуга класності в Ангарі | Оверлей у бою |
| ![Смуга прогресу — Ковзне середнє](assets/screenshots/progress_moving_average.png) | ![Смуга прогресу — Ефективність шкоди](assets/screenshots/progress_damage_efficiency.png) |
| Смуга прогресу — Ковзне середнє | Смуга прогресу — Ефективність шкоди |
| ![Графік тренду класності в Ангарі](assets/screenshots/trend_ua.png) |  |
| Графік тренду класності в Ангарі |  |

## Що показує

### Смуга класності в Ангарі

Смуга за перцентилем у панелі параметрів техніки з позначками на **65% / 85% / 95%** —
пороги 1 / 2 / 3 знаків — кожна намальована рідною іконкою знака з клієнта. Кожна позначка
підписана комбінованою шкодою, потрібною для цього знака, а смуга заповнюється до вашого
поточного стану. Над нею — ваша поточна середня комбінована шкода й поточний відсоток знака
для обраної техніки.

**Ctrl+перетягування** переміщує віджет у будь-яке місце екрана (утримуйте **Shift**, щоб
зафіксувати перетягування за однією віссю). Місце, де ви його відпустили, запам'ятовується; у
панелі також є числові поля позиції та параметр **Слідувати за каруселлю** — див. Налаштування.

Наведення на підказку позначки в смузі також показує тижневий графік тренду ковзного
середнього класності — крапки для кожного бою на фіксованій вісі перцентиля, лінії позначок
на 65% / 85% / 95% / 100%, розділювачі днів і підпис ковзного середнього на кінець кожного дня.

### Оверлей у бою

Компактний оверлей над HUD із двома рядками (необов'язковий третій рядок показує зараховану
допомогу — див. Налаштування):

- **Поточна комбінована шкода проти прогнозованого середнього** — число забарвлене за знаком
  (червоне нижче прогнозу, біле на рівні, зелене вище).
- **Прогнозований відсоток знака** зі знаком зміни відносно початку бою.

### Смуга прогресу в бою *(вимкнено за замовчуванням)*

Широка смуга в **центрі екрана**, окрема від кутового оверлея, малюється **горизонтально**
(початкове розташування) або **вертикально** поруч із мінікартою — виберіть **Орієнтацію** в
Налаштуваннях. За замовчуванням вона з'являється, коли є що показати, тримається кілька секунд
(п'ять за замовчуванням, налаштовується в Налаштуваннях) і зникає сама, а **утримання Alt**
також показує її — незалежно від власного параметра оверлея з натисканням Alt; налаштування
нижче дозволяють вимкнути будь-який із цих тригерів або закріпити смугу на екрані назавжди.
Смуга ніколи не перехоплює керування мишею й залишається схованою, поки відкрита таблиця
результатів (**Tab**), під час спостереження за іншим гравцем і доки у вас немає техніки.
Налаштування дозволяють намалювати її **Великою** та вимкнути плавні переходи, щоб вона
з'являлася й зникала миттєво.

За замовчуванням смуга розташована у **Фіксованій** вбудованій точці, обраній автоматично за
Орієнтацією, — по центру над журналом ушкоджень у горизонтальному режимі, поруч із мінікартою у
вертикальному. Перемкніть **Прив'язку** на **Вільну** в Налаштуваннях, щоб розблокувати її, а тоді
**Ctrl+перетягуванням** перемістіть смугу в будь-яке місце екрана — позиція спільна для обох
режимів і запам'ятовується; у панелі також є числові поля X/Y для неї, неактивні, поки Прив'язка —
Фіксована — див. Налаштування.

Увімкніть її в Налаштуваннях і виберіть **одну** з двох смуг — вони взаємовиключні:

- **Ефективність шкоди** *(за замовчуванням)* — шкода цього бою відносно всіх чотирьох вимог
  (**65% / 85% / 95% / 100%**), розкладених на чотири рівні чверті, з підсвіченими вимогами, які
  ви вже пройшли. Не потребує базового значення й з'являється сама щоразу, коли ваша шкода в
  цьому бою досягає нового максимуму.
- **Ковзне середнє** — де перебуває ваша прогнозована середня комбінована шкода за кар'єру між
  наявною позначкою та вимогою наступної, з підписаним внеском цього бою поруч. Підпис наступної
  позначки також показує **прогноз**: скільки ще боїв потрібно у вашому поточному темпі, щоб її
  досягти. З'являється щоразу, коли цей прогноз змінюється. Потребує базового значення кар'єри,
  тож у реплеях, а також після повторного входу, доки ви не зайшли в Ангар, вона нічого не показує.

Не обов'язково відкривати Налаштування, щоб перемкнути смугу посеред бою: натисніть **Клавішу
зміни режиму** (за замовчуванням **K**, перепризначувана), щоб перемкнути режим смуги поточної
машини — мод запам'ятовує вибір для кожної машини, а смуга перезавантажується і з'являється знову
через кілька секунд після перемикання. **Автоматичне перемикання режиму** може зробити те саме
самостійно: щойно прогрес знаків машини перед боєм досягає вказаного вами відсотка, її режим
перемикається один раз, так само як і клавішею.

Три перемикачі вирішують, **коли** вона з'являється: **Події** (відстежувана подія в бою показує
її, увімкнено за замовчуванням), **Натискання Alt** (утримання Alt показує її, увімкнено за
замовчуванням) і **Завжди** (закріплює її на екрані назавжди й робить два інші перемикачі
неактивними, вимкнено за замовчуванням). Окремий перемикач **Переходи** вирішує, **як** вона
рухається, коли з'являється, — з плавним затуханням і зсувом за замовчуванням, або миттєво, якщо
його вимкнути, — а також як довго вона тримається, перш ніж почати зникати.

Позиція кутового оверлея незмінна; Фіксована позиція смуги в центрі екрана залежить від
Орієнтації, або стає повністю рухомою, щойно ви перемкнете Прив'язку на Вільну — див. розділ
*Розташування* в Налаштуваннях. На техніці, для якої не вдалося отримати пороги знаків, жодна зі
смуг не малюється — смуга в Ангарі все одно працює.

## Сумісність

| Вимога | Деталі |
|--------|--------|
| **Гра** | World of Tanks **EU 2.4.1.0** (глобальний клієнт Wargaming). Зібрано для цієї версії. |
| **Обов'язково** | **OpenWG GameFace** 1.2.2+ — встановіть першим, інакше віджет не з'явиться. З [wgmods.net](https://wgmods.net) або [gitlab.com/openwg/wot.gameface](https://gitlab.com/openwg/wot.gameface). |

## Завантаження та встановлення

**Найпростіше — інсталятор в один клік (Windows).** Завантажте найновіший
**`MoECalculator-Setup-<version>.exe`** зі сторінки
[**релізів на GitHub**](https://github.com/drizzer14/moe-calculator/releases) і запустіть
(спершу закрийте гру). Він знаходить папку World of Tanks, встановлює мод у `mods\<version>\`
і додає вкладені залежності — **OpenWG GameFace**, **Aslain ModMenu** та **ModsList** — для
тих, яких ще немає. Під час кожного запуску
він також перевіряє GitHub і пропонує завантажити найновіший інсталятор, тож збережена копія
залишається актуальною.

**Встановлення вручну.** Візьміть `com.14th_ua.moe_calculator_<version>.wotmod` з тієї ж
сторінки релізів і дотримуйтесь **[`INSTALL.md`](./INSTALL.md)** — там описано ручне
копіювання, перевірку роботи, усунення несправностей і видалення.

## Налаштування

Мод додає панель до внутрішньоігрового **меню налаштувань модів**, яке надає
**Aslain ModMenu (MSA)** — стандартний застосунок налаштувань, що йде разом з інсталятором.
Якщо MSA не завантажено, мод усе одно працює з увімкненими за замовчуванням віджетами — просто
не буде панелі.

Панель згрупована в іменовані **категорії**, кожна — жирний заголовок, за яким ідуть параметри цієї
функції, тож власний перемикач кожної функції називається просто **Увімкнено**. Стовпець 1 містить
оверлей у бою та все, що стосується Ангара; стовпець 2 — цілу функцію смуги прогресу в центрі
екрана. У панелі також є зображення-перегляди обох віджетів, які оновлюються разом із параметрами,
що впливають на їхній вигляд:

| Налаштування | За замовчуванням | Що робить |
|---|---|---|
| *Бойовий калькулятор* | — | Заголовок категорії для оверлею в бою. |
| **Увімкнено** | Увімк. | Показує накладання класності наживо під час бою. |
| ↳ **Натискання Alt** | Вимк. | Показує накладання лише поки утримується **Alt**; коли вимкнено — показує постійно. |
| ↳ **Рядок зарахованої допомоги** | Увімк. | Додає третій рядок накладання: більше з допомоги гусеницями, засвітом чи оглушенням, з піктограмою переважного типу. |
| *Віджет в ангарі* | — | Заголовок категорії для смуги в Ангарі. |
| **Увімкнено** | Увімк. | Показує смугу процентиля класності в Ангарі на вибраній машині. |
| *Розташування* (Ангар) | — | Підкатегорія для позиції віджета в Ангарі. |
| **Слідувати за каруселлю** | Увімк. | Закріплений віджет продовжує зміщуватися по вертикалі разом із каруселлю техніки (один / два ряди), щоб ніколи її не перекривати. |
| **Горизонталь (лівий X)** / **Вертикаль (верхній Y)** | 0 = авто | Відстань закріпленого віджета від лівого / верхнього краю екрана в пікселях. **Ctrl+перетягування** закріплює віджет (**Shift** фіксує за однією віссю). |
| *Прогрес у бою* | — | Заголовок категорії для смуги прогресу в центрі екрана — тепер окремий стовпець, не пов'язаний із Бойовим калькулятором. |
| **Увімкнено** | Вимк. | Показує смугу в центрі екрана. Режим і масштаб виберіть нижче, а коли вона з'являється — трьома перемикачами під ними. |
| ↳ **Події** | Увімк. | Самостійно показує смугу, щойно відбувається відстежувана подія в бою, і знову ховає її. Ігнорується, поки увімкнено **Завжди**. |
| ↳ **Натискання Alt** | Увімк. | Показує смугу, лише поки утримується **Alt**. Ігнорується, поки увімкнено **Завжди**. |
| ↳ **Завжди** | Вимк. | Залишає смугу на екрані назавжди; вона ніколи не зникає. Має пріоритет над обома перемикачами вище, які стають неактивними, поки цей увімкнено. |
| **Режим** | Ефективність шкоди | Вибір між двома взаємовиключними режимами — **Ефективність шкоди** *(за замовчуванням)* та **Ковзне середнє** — пара радіокнопок в один рядок. |
| **Клавіша зміни режиму** | K | Клавіша в бою, яка перемикає режим смуги поточної машини; мод запам'ятовує вибір для кожної машини окремо. |
| **Автоматичне перемикання режиму** | 100% (вимк.) | Щойно прогрес знаків машини перед боєм досягає цього відсотка, її режим перемикається один раз самостійно — так само як клавішею перемикання. 100% вимикає функцію. |
| **Масштаб** | Стандартний | **Стандартний** або **Великий**. Великий малює помітно більшу смугу — той самий вигляд, просто більша. |
| **Ковзне середнє: показувати %** | Увімк. | Показує ваш поточний відсоток відмітки майстерності з урахуванням цього бою в дужках поруч із поточною шкодою на смузі «Ковзне середнє». |
| **Ковзне середнє: показувати зміну** | Увімк. | Показує у вигляді (+N), наскільки цей бій змінює ваше ковзне середнє, поруч із поточною шкодою на смузі «Ковзне середнє». |
| **Ефективність шкоди: показувати %** | Увімк. | Показує відсоток відмітки майстерності, якого вартує сама лише шкода цього бою, в дужках поруч із поточною шкодою на смузі «Ефективність шкоди». |
| **Ефективність шкоди: показувати зміну** | Увімк. | Показує на смузі «Ефективність шкоди» спалах +N зі шкодою вашого останнього влучання. |
| *Переходи* | — | Заголовок категорії для того, як анімується смуга в центрі екрана і як довго вона тримається на екрані. |
| **Увімкнено** | Увімк. | Смуга з'являється та зникає з плавним затуханням і зсувом. Вимкніть, щоб вона з'являлася й зникала **миттєво**; смуга все одно показується й ховається, лише без анімації. |
| ↳ **Події** | Увімк. | Анімує смугу, коли її показує подія в бою (тик шкоди), і коли вона знову ховається. |
| ↳ **Натискання Alt** | Увімк. | Анімує показ по **Alt**. Вимкнено — як у власному інтерфейсі гри, який не анімує по Alt. |
| ↳ **Тривалість показу (с)** | 5 | Скільки секунд смуга тримається на екрані, перш ніж почати зникати (або зникнути одразу, якщо Переходи вимкнено). Діапазон 1–30. |
| *Розташування* (смуга) | — | Заголовок категорії для орієнтації, прив'язки й позиції смуги в центрі екрана. |
| **Орієнтація** | Горизонтальна | **Горизонтальна** (початкове розташування) або **Вертикальна**, яка малює смугу вертикально, з розміром для розміщення поруч із мінікартою. |
| **Прив'язка** | Фіксована | **Фіксована** — вбудована точка смуги, обрана автоматично за Орієнтацією, — або **Вільна**, позиція без прив'язки, яку ви задаєте перетягуванням або лічильниками нижче. |
| **Горизонталь (лівий X)** / **Вертикаль (верхній Y)** | 0 = авто | Зсув смуги в центрі екрана в пікселях, спільний для обох режимів. Неактивний, поки **Прив'язка** не **Вільна** — **Ctrl+перетягування** смуги встановлює його, коли вона вільна. |

Зняття позначки з головного перемикача (власне **Увімкнено** у **Бойовому калькуляторі**, у
**Прогресі в бою** й у **Переходах**) робить його вкладені рядки неактивними; параметри Ангара та
категорія **Розташування** смуги головного не мають. **Завжди**, своєю чергою, робить неактивними
**Події** та **Натискання Alt** одразу над ним, щойно він увімкнений. **Режим**, **Клавіша зміни
режиму**, **Автоматичне перемикання режиму**, **Масштаб**, **Орієнтація** та **Прив'язка**
розташовані поряд із головним перемикачем своєї категорії, а не під ним, тож лишаються активними,
навіть коли сама функція вимкнена, — просто їм нічого впливати, доки її не увімкнено. Лічильники
позиції смуги (і перетягування) стають неактивними, щойно **Прив'язка** — **Фіксована**, адже
задавати нічого, поки смуга у вбудованій точці. **0 / 0** — стандартна позиція в правому нижньому
куті для віджета в Ангарі, а для смуги прогресу в центрі екрана — стандартна (авто) позиція в
режимі Вільна; обидві повертає кнопка **скидання** мода в панелі. Параметри позиції Ангара
стосуються лише його віджета; категорія **Розташування** смуги стосується смуги прогресу в центрі
екрана (спільна для обох режимів) — позиція кутового оверлея незмінна. Що показує кожен режим
смуги прогресу і яке базове значення кар'єри потрібне для **Ковзного середнього** — описано вище в
розділі *Смуга прогресу в бою*.

## Примітки

- **Після оновлення гри** перемістіть `.wotmod` у нову папку `mods\<версія>\`. Нова версія
  клієнта може потребувати перезібраного мода — перевіряйте сторінку релізів.

## Джерело даних класності

Пороги знаків для кожної техніки (комбінована шкода, потрібна для знака) беруться з
**офіційного API Wargaming** — це реальний розподіл шкоди, тож числа автентичні й актуальні.
Пороги кешуються локально, тож перемикання техніки миттєве. Відсоток між знаками в бою
інтерполюється так само, як і власний відсоток класності Wargaming, — щоб якнайточніше
збігатися з тим, що показала б сама гра.

## Модпаки та ліцензія

Вільно використовувати, поширювати та включати в модпаки, доки це залишається безкоштовним і
зазначає автора (**14th_ua**) з посиланням на цей репозиторій — див. [`LICENSE.md`](./LICENSE.md).
Для модпаків додавайте лише `.wotmod` і вкажіть OpenWG GameFace як обов'язкову залежність; не
вкладайте GameFace самі.

## Розробка

Збірка, розгортання, тести та структура репозиторію описані в [`CLAUDE.md`](./CLAUDE.md) (а
цикл розробки — у [`tools/dev/README.md`](./tools/dev/README.md)).
