# Where the observations came from

I manually read the blue Test-series circle centres in Figure 3A of Li et al. (2022), *A multicenter randomized trials to compare the bioequivalence and safety of a generic doxorubicin hydrochloride liposome injection with Caelyx in advanced breast cancer*, Frontiers in Oncology 12:1070001. DOI: [10.3389/fonc.2022.1070001](https://doi.org/10.3389/fonc.2022.1070001). [Article and figure](https://www.frontiersin.org/journals/oncology/articles/10.3389/fonc.2022.1070001/full#F3).

These are **approximate published group means**, not raw measurements or individual patient data. The six late samples are well separated in the picture; I omitted the crowded early markers rather than invent readings. The series measures liposome-encapsulated doxorubicin, not free drug or tumour uptake. Figure legend: Test N=44. The authors report a 50 mg/m² dose infused over 90 minutes. Sampling times come from the paper's blood-sample collection section, rather than guessed x coordinates.

## Reproduce the reading

Use the publisher's [1654 by 650 pixel JPEG](https://www.frontiersin.org/files/Articles/1070001/fonc-12-1070001-HTML/image_m/fonc-12-1070001-g003.jpg). Pixel coordinates in the CSV use the upper-left corner as (0,0). In panel A, the 0 and 40 µg/mL ticks are approximately y=508 and y=65. Convert each circle centre by `C=(508-y)*40/(508-65)` and round to 0.1 µg/mL. The horizontal calibration is approximately x=149 at 0 h and x=242 at 50 h; the CSV uses the exact scheduled times instead. Marker reading is uncertain by roughly 2 pixels (0.18 µg/mL), before biological variability. This is a reading estimate, not a statistical error bound. Error-bar endpoints were not extracted and are not used as fit weights.

The last marker centre and axis ticks can be a few pixels ambiguous. Modest changes in digitization affect the fitted values, especially the late tail. The toolkit does not treat the CSV as more precise than the graph.

The article is copyright © 2022 Li, Qi, Wang and colleagues, published under Creative Commons Attribution (CC BY); see its copyright statement. The CSV is a rounded numerical adaptation of Figure 3A with this attribution. The original figure is linked, not redistributed. This dataset is committed so tests and figures work offline.
