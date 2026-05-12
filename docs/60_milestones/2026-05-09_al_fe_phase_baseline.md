# Milestone: baseline Al и standalone Fe4Al13

Дата: 2026-05-09.

## Итог

- Подтверждён baseline чистого Al на `Al_zhou.eam.alloy`.
- Скачана публичная CIF-структура Al13Fe4 из COD `1571554`.
- Структура сконвертирована в LAMMPS data с типами Al=1, Fe=2.
- Скачан и подключён MEAM Jelinek/Groh/Horstemeyer 2012 с явными Al-Fe cross-interactions.
- Standalone Fe4Al13 прошёл minimization, triclinic `box/relax` и NPT 300 K / 0 bar на 5000 steps без `ERROR`, `nan` и `lost atoms`.

## Риски

- Fe4Al13 проверен пока только на 102-атомной ячейке; мгновенное давление сильно флуктуирует.
- OVITO conda package установлен, но GUI падает с `dyld`, а Python module `ovito` не импортируется.
- Интерфейс не собран: нужен выбор ориентаций и mismatch-анализ.

## Следующий шаг

Сделать `analysis/python/build_flat_interface.py` для перебора ориентаций Al/Fe4Al13, оценки 2D mismatch и только затем собрать маленький ненагруженный интерфейс.
