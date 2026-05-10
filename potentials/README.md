# Межатомные потенциалы

| Потенциал | Тип | Элементы | Источник | Файлы | Запустился? | Держит Al? | Держит Fe4Al13? | Комментарий |
|---|---|---|---|---|---|---|---|---|
| Zhou Al | EAM/alloy | Al | локально загружен ранее | `potentials/eam/Al_zhou.eam.alloy` | да | да | нет, нет Fe и Al-Fe | Использован только для baseline чистого Al. Не подходит для Al-Fe интерфейса. |
| Jelinek/Groh/Horstemeyer et al. 2012 | MEAM | Al, Si, Mg, Cu, Fe | NIST IPR / OpenKIM; DOI `10.1103/PhysRevB.85.245102` | `potentials/meam/Jelinek_2012/Jelinek_2012_meamf`, `potentials/meam/Jelinek_2012/Jelinek_2012_meam.alsimgcufe` | да | не перепроверялся в этой сессии для pure Al | sanity-run да | Содержит Al-Fe cross-interaction. Подходит как baseline-кандидат, но не как окончательная физическая валидация Fe4Al13. |

## MEAM pair_coeff

Проверено по файлам потенциала и тестовому архиву NIST:

```lammps
pair_style meam
pair_coeff * * ../../potentials/meam/Jelinek_2012/Jelinek_2012_meamf AlS SiS MgS CuS FeS ../../potentials/meam/Jelinek_2012/Jelinek_2012_meam.alsimgcufe AlS FeS
```

Порядок LAMMPS atom types для текущего `al13fe4.data`:

```json
{
  "Al": 1,
  "Fe": 2
}
```
