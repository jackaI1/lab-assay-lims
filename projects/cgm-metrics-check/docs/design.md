# Calculation choices

I use one explicitly declared, regular sampling interval for one sensor series at a time. Each reading occupies one expected timestamp, and I count only readings in the requested half-open window [start, end). This makes the denominator independent of where the file happens to start or stop. Off-grid readings are rejected, rather than resampled or interpolated. Different sensor streams must be analyzed separately.

I considered filling missing readings or weighting each reading until the next one. Both could let a reading beside a long outage stand for time that was never measured. I instead leave slots missing and show the coverage with every metric.

Identical duplicate timestamps count once. Conflicting values at the same instant invalidate that slot, even if one appears more plausible. Invalid, absent or unrecognized quantities are rejected at import. Explicit mixed units are flagged and converted to mg/dL for calculation, while the original quantity is retained for export. The conversion is 18.0182 mg/dL per mmol/L. Units are never guessed from the size of a number.

I use reading proportions for time in range on the fixed grid, the arithmetic mean and population standard deviation. Metric values are rounded to ten decimal places for reproducible JSON across supported Python versions; the input quantities are not rounded. CV is population standard deviation divided by mean, multiplied by 100. Time in range includes 70 and 180 mg/dL; the nested low and high bands use 54 and 250 mg/dL. The GMI formula is 3.31 + 0.02392 times the mean in mg/dL. GMI is not a laboratory A1C measurement.

Reports refuse every metric below 70% coverage. Normal reports also require an analysis window of at least 14 days. Short windows are allowed only through an explicitly labeled exploratory option used by hand calculations and tests; that option never relaxes the coverage gate. A sufficient overall count does not establish representative day/night coverage or clinical suitability. Daily coverage and missing runs remain visible.

FHIR exports contain original validated readings, including values whose timestamp conflicts, with a source-row identifier. They are source observations, not the accepted-slot dataset. They contain no invented patient identifier. The source's timezone is unknown; the public example uses a disclosed UTC placeholder to preserve relative intervals and enable a syntactically valid FHIR timestamp. It does not establish actual UTC collection time.

This is a data-checking project, not a medical device, and it gives no treatment advice.
