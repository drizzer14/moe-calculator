# 14th_ua's MoE Calculator — World of Tanks mod

Track your **Marks of Excellence (MoE)** progress for the vehicle you have selected,
in the Garage and live in battle. In the Garage it draws a percentile bar with the
**1 / 2 / 3-mark milestones (65% / 85% / 95%)** using the game's own mark art, showing
the combined damage each mark needs plus your current average combined damage and mark
percentage. In battle it adds a small, input-transparent overlay over the HUD with your
live performance against your own projection.

**English** · [Українська](#14th_uas-moe-calculator--українська)

## What it shows

- **Garage MoE bar** — a percentile axis (0–100) with milestone ticks at 65 / 85 / 95
  (= 1 / 2 / 3 marks), each drawn with the vehicle's mark art and labelled with the
  combined damage it requires.
- **Current standing** — a readout of your current average combined damage and current
  mark percentage for the selected vehicle, at full precision.
- **In-battle overlay** — a compact HUD overlay showing your **live combined damage vs
  your projected average** (red below / white at / green above), and your **projected MoE
  percentage** with the signed change versus where you started the battle. It never
  intercepts battle input.

## Compatibility

| Requirement | Detail |
|-------------|--------|
| **Game** | World of Tanks **EU 2.3.0.1** (Wargaming global client). Built and tested against this version. |
| **Required** | **OpenWG GameFace** 1.1.6+ — install it first, or the widget will not appear. From [wgmods.net](https://wgmods.net) or [gitlab.com/openwg/wot.gameface](https://gitlab.com/openwg/wot.gameface). |
| **Optional** | **ModsSettingsAPI** 1.7.0+ — bundled by the installer as a common dependency. This mod has no in-game options yet, so it works with or without it. |

## Download & install

**Easiest — the one-click installer (Windows).** Download the latest
**`MoECalculator-Setup-<version>.exe`** from the
[**GitHub Releases**](https://github.com/drizzer14/moe-calculator/releases) page and run
it (close the game first). It finds your World of Tanks folder, installs the mod into
`mods\<version>\`, and adds **OpenWG GameFace** and **ModsSettingsAPI** if you don't
already have them. On each run it also checks GitHub and offers to fetch the newest
installer, so a copy you keep around stays current.

**Manual installation.** Grab `com.14th_ua.moe_calculator_<version>.wotmod` from the same
Releases page and follow **[`INSTALL.md`](./INSTALL.md)** — it covers the manual copy,
verifying it works, troubleshooting, and uninstalling.

## Settings

This mod has no in-game options yet — the Garage bar and the in-battle overlay simply show
automatically. **ModsSettingsAPI** is bundled as a common dependency but is not required.

## Notes & limitations

- **Event / special-mode hangars** may not expose the panel the Garage bar attaches to, so
  it won't show there. It returns in the normal Garage.
- **After a game update**, move the `.wotmod` to the new `mods\<version>\` folder. A new
  client version may need a rebuilt mod — check the Releases page.

## Modpacks & license

Free to use, redistribute, and include in modpacks as long as it stays free and credits the
author (**14th_ua**) with a link back to this repository — see [`LICENSE.md`](./LICENSE.md).
For modpacks, add only the `.wotmod` and list OpenWG GameFace as a required dependency; don't
bundle GameFace or ModsSettingsAPI yourself.

## Contributing / developers

Building, deploying, testing, and the repo layout are documented in
[`CLAUDE.md`](./CLAUDE.md) (and the dev loop in [`tools/dev/README.md`](./tools/dev/README.md)).

---

# 14th_ua's MoE Calculator — Українська

Відстежуйте прогрес **Знаків Класності (MoE)** для обраної техніки — в Ангарі та наживо в
бою. В Ангарі малюється смуга за перцентилем із позначками **1 / 2 / 3 знаків (65% / 85% /
95%)** рідними іконками гри: показано комбіновану шкоду, потрібну для кожного знака, а також
вашу поточну середню комбіновану шкоду й відсоток знака. У бою додається невеликий оверлей
над HUD, який не перехоплює керування, із вашими показниками відносно власного прогнозу.

[English](#14th_uas-moe-calculator--world-of-tanks-mod) · **Українська**

## Що показує

- **Смуга MoE в Ангарі** — вісь за перцентилем (0–100) із позначками на 65 / 85 / 95
  (= 1 / 2 / 3 знаки), кожна намальована відповідною іконкою знака й підписана комбінованою
  шкодою, яка для неї потрібна.
- **Поточний стан** — ваша поточна середня комбінована шкода й поточний відсоток знака для
  обраної техніки, з повною точністю.
- **Оверлей у бою** — компактний оверлей над HUD: **поточна комбінована шкода проти вашого
  прогнозованого середнього** (червоний нижче / білий на рівні / зелений вище) та
  **прогнозований відсоток MoE** зі знаком зміни відносно початку бою. Ніколи не перехоплює
  керування в бою.

## Сумісність

| Вимога | Деталі |
|--------|--------|
| **Гра** | World of Tanks **EU 2.3.0.1** (глобальний клієнт Wargaming). Зібрано й перевірено для цієї версії. |
| **Обов'язково** | **OpenWG GameFace** 1.1.6+ — встановіть першим, інакше віджет не з'явиться. З [wgmods.net](https://wgmods.net) або [gitlab.com/openwg/wot.gameface](https://gitlab.com/openwg/wot.gameface). |
| **Необов'язково** | **ModsSettingsAPI** 1.7.0+ — додається інсталятором як поширена залежність. Цей мод поки не має налаштувань у грі, тож працює як із нею, так і без неї. |

## Завантаження та встановлення

**Найпростіше — інсталятор в один клік (Windows).** Завантажте найновіший
**`MoECalculator-Setup-<version>.exe`** зі сторінки
[**релізів на GitHub**](https://github.com/drizzer14/moe-calculator/releases) і запустіть
(спершу закрийте гру). Він знаходить папку World of Tanks, встановлює мод у `mods\<version>\`
і додає **OpenWG GameFace** та **ModsSettingsAPI**, якщо їх ще немає. Під час кожного запуску
він також перевіряє GitHub і пропонує завантажити найновіший інсталятор, тож збережена копія
залишається актуальною.

**Встановлення вручну.** Візьміть `com.14th_ua.moe_calculator_<version>.wotmod` з тієї ж
сторінки релізів і дотримуйтесь **[`INSTALL.md`](./INSTALL.md)** — там описано ручне
копіювання, перевірку роботи, усунення несправностей і видалення.

## Налаштування

Цей мод поки не має параметрів у грі — смуга в Ангарі та оверлей у бою просто показуються
автоматично. **ModsSettingsAPI** додається як поширена залежність, але не є обов'язковою.

## Примітки та обмеження

- **Подієві та спеціальні ангари** можуть не надавати панель, до якої кріпиться смуга в
  Ангарі, тож там вона не з'явиться. У звичайному Ангарі вона повертається.
- **Після оновлення гри** перемістіть `.wotmod` у нову папку `mods\<версія>\`. Нова версія
  клієнта може потребувати перезібраного мода — перевіряйте сторінку релізів.

## Модпаки та ліцензія

Вільно використовувати, поширювати та включати в модпаки, доки це залишається безкоштовним і
зазначає автора (**14th_ua**) з посиланням на цей репозиторій — див. [`LICENSE.md`](./LICENSE.md).
Для модпаків додавайте лише `.wotmod` і вкажіть OpenWG GameFace як обов'язкову залежність; не
вкладайте GameFace чи ModsSettingsAPI самі.

## Розробка

Збірка, розгортання, тести та структура репозиторію описані в [`CLAUDE.md`](./CLAUDE.md) (а
цикл розробки — у [`tools/dev/README.md`](./tools/dev/README.md)).
