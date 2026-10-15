==============================================================
 14th_ua's MoE Calculator  -  World of Tanks mod (EU 2.4.1.0)
 by 14th_ua                 version {VERSION}
==============================================================

This archive bundles the mod and its dependencies. Extract it into
your World of Tanks folder and restart the game.

WHAT'S IN THE BOX
    com.14th_ua.moe_calculator_{VERSION}.wotmod      the mod
    net.openwg.gameface_1.2.2.wotmod                 REQUIRED dependency
    aslain.modmenu_2.1.04.wotmod                     optional (settings panel)
    me.poliroid.modslistapi_1.8.0.wotmod             optional (Modification list window)


==============================================================
 ENGLISH
==============================================================

WHAT IT DOES
    Shows your Marks of Excellence (MoE) progress for the vehicle
    you have selected. In the Garage it draws a percentile bar with
    the 1/2/3-mark milestones (65% / 85% / 95%) and the combined
    damage each one needs, plus your current average combined damage
    and mark percentage. Ctrl+drag the Garage bar to move it anywhere
    on screen (Shift locks the drag to one axis). Hovering the mark
    tooltip also shows a weekly moving-average MoE trend chart, with
    per-battle dots on a fixed percentile axis, mark lines at 65 / 85 /
    95 / 100 %, day dividers, and an end-of-day average label per day.
    In battle it adds a
    small overlay over the HUD showing your live combined damage
    against your projected average, and your projected MoE percentage
    with the change versus where you started the battle.

    It can also show a transient bar in the centre of the screen
    during battle (OFF by default, turn it on in the settings panel),
    drawn either horizontally or vertically beside the minimap. It
    fades in, holds for a few seconds (five by default, adjustable)
    and fades out on its own; hold Alt to bring it up at any time (or
    turn on "Always" in settings to keep it up permanently). Pick one
    of two bars: Damage Efficiency (the default; this battle's damage
    against the 65 / 85 / 95 / 100 % requirements) or Moving Average
    (your projected average between the mark you hold and the next
    mark's requirement, plus this battle's contribution and an ETA in
    battles to the next mark). Press K in battle (rebindable in
    settings) to flip the current vehicle's bar mode, or let it switch
    automatically once a vehicle's mark progress crosses a percentage
    you set. By default the bar sits at a built-in spot; switch
    Alignment to Free in settings to Ctrl+drag it anywhere on screen
    (shared by both bars).

INSTALL  (2 steps)
    1) Extract this archive into your World of Tanks folder, so the
       files land in:
           <World of Tanks>\mods\2.4.0.0\
    2) Fully restart the game client (exit and relaunch).

    The version folder (2.4.0.0) must match your installed client
    version. If yours differs, move the .wotmod files into the
    matching mods\<your-version>\ folder.

DEPENDENCIES
    OpenWG GameFace is REQUIRED - the widget will not appear without
    it. If you already run it, keep your existing copy.

    Aslain ModMenu is OPTIONAL - it adds the in-game settings panel
    where you turn the Garage and Battle widgets on or off, enable the
    centre-screen bar and pick its variant, orientation and position,
    and set the Garage widget's position. Without it the mod still
    works with both widgets enabled and the centre-screen bar off.
    Keep your existing copy if you already run it.

NETWORK
    The mod calls Wargaming's own public API (api.worldoftanks.eu) to
    fetch the real Marks-of-Excellence damage thresholds for your
    vehicles. No other data is sent or collected.

UNINSTALL
    Delete com.14th_ua.moe_calculator_{VERSION}.wotmod from
    mods\<version>\ and restart. Leave GameFace if other mods use it.

    Built for the Wargaming EU/global client, NOT the Lesta / Mir
    Tankov (RU) client.


==============================================================
 УКРАЇНСЬКА
==============================================================

ЩО ЦЕ РОБИТЬ
    Показує ваш прогрес Знаків Класності (MoE) для обраної техніки.
    В Ангарі малює смугу за перцентилем із позначками 1/2/3 знаків
    (65% / 85% / 95%) та комбінованою шкодою, потрібною для кожного,
    а також вашу поточну середню комбіновану шкоду й відсоток знака.
    Ctrl+перетягування переміщує смугу в Ангарі в будь-яке місце
    екрана (Shift фіксує перетягування за однією віссю). Наведення на
    підказку позначки також показує тижневий графік тренду ковзного
    середнього класності: крапки по кожному бою на фіксованій вісі
    перцентиля, лінії позначок на 65 / 85 / 95 / 100 %, розділювачі
    днів і підпис середнього на кінець кожного дня. У бою додає
    невеликий оверлей над HUD: поточна комбінована шкода проти вашого
    прогнозованого середнього та прогнозований відсоток MoE зі зміною
    відносно початку бою.

    Також може показувати тимчасову смугу в центрі екрана під час бою
    (ВИМКНЕНО за замовчуванням, увімкніть у панелі налаштувань),
    намальовану горизонтально або вертикально поруч із мінікартою.
    Вона з'являється, тримається кілька секунд (п'ять за замовчуванням,
    налаштовується) і зникає сама; утримуйте Alt, щоб показати її
    будь-коли (або увімкніть "Завжди" в налаштуваннях, щоб тримати її
    сталою). Виберіть одну з двох смуг: Ефективність шкоди (за
    замовчуванням; шкода цього бою відносно вимог 65 / 85 / 95 / 100 %)
    або Ковзне середнє (ваша прогнозована середня між наявною
    позначкою та вимогою наступної, плюс внесок цього бою та прогноз
    у боях до наступної позначки). Натисніть K у бою (можна
    перепризначити в налаштуваннях), щоб перемкнути режим смуги
    поточної машини, або дозвольте їй перемикатися автоматично, щойно
    прогрес знаків машини перевищить вказаний вами відсоток. За
    замовчуванням смуга розташована у вбудованій точці; перемкніть
    Прив'язку на Вільну в налаштуваннях, щоб перетягувати її Ctrl'ом у
    будь-яке місце екрана (спільно для обох смуг).

ВСТАНОВЛЕННЯ  (2 кроки)
    1) Розпакуйте архів у теку World of Tanks так, щоб файли
       потрапили в:
           <World of Tanks>\mods\2.4.0.0\
    2) Повністю перезапустіть клієнт гри (вихід і повторний запуск).

    Тека версії (2.4.0.0) має збігатися з версією вашого клієнта.
    Якщо вона інша - перемістіть файли .wotmod у теку
    mods\<ваша-версія>\, що відповідає вашій версії.

ЗАЛЕЖНОСТІ
    OpenWG GameFace ОБОВ'ЯЗКОВИЙ - без нього віджет не з'явиться.
    Якщо він уже стоїть, лишіть свою копію.

    Aslain ModMenu НЕОБОВ'ЯЗКОВИЙ - додає ігрову панель налаштувань,
    де можна вмикати/вимикати віджети в Ангарі та в бою, увімкнути
    смугу в центрі екрана й вибрати її варіант, орієнтацію та позицію,
    а також задати позицію віджета в Ангарі. Без нього мод працює з
    обома увімкненими віджетами й вимкненою смугою в центрі екрана.
    Якщо він уже стоїть, лишіть свою копію.

МЕРЕЖА
    Мод звертається до публічного API Wargaming (api.worldoftanks.eu),
    щоб отримати реальні пороги Знаків Класності для вашої техніки.
    Жодні інші дані не надсилаються й не збираються.

ВИДАЛЕННЯ
    Видаліть com.14th_ua.moe_calculator_{VERSION}.wotmod з
    mods\<версія>\ і перезапустіть. GameFace лишіть, якщо його
    використовують інші моди.

    Зроблено для клієнта Wargaming EU/global, НЕ для клієнта
    Lesta / Мир танків (RU).
