package com.jacklai.labresults;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

class ResultCsvTest {
    private final ResultCsv csv = new ResultCsv();

    private LabResult result(String patientId, String status, int revision) {
        return new LabResult(UUID.fromString("22222222-2222-4222-8222-222222222222"), patientId, "LAB-001",
                LabTest.POTASSIUM, new BigDecimal("0.0001"), LabTest.POTASSIUM.unit(),
                Instant.parse("2026-01-15T10:30:00Z"), status, revision, Instant.parse("2026-01-15T11:00:00Z"));
    }

    @Test void emptyListStillWritesHeaderOnly() {
        assertThat(csv.export(List.of())).isEqualTo(ResultCsv.HEADER + "\r\n");
    }

    @Test void writesOneRowPerResultWithPlainDecimalsAndUnits() {
        String[] lines = csv.export(List.of(result("SYN-001", "AMENDED", 2))).split("\r\n");
        assertThat(lines).hasSize(2);
        assertThat(lines[0]).isEqualTo(ResultCsv.HEADER);
        assertThat(lines[1]).isEqualTo("22222222-2222-4222-8222-222222222222,SYN-001,LAB-001,POTASSIUM,"
                + "0.0001,mmol/L,2026-01-15T10:30:00Z,AMENDED,2,2026-01-15T11:00:00Z");
    }

    @ParameterizedTest
    @CsvSource({"GLUCOSE,mmol/L", "POTASSIUM,mmol/L", "HEMOGLOBIN,g/dL"})
    void writesEveryCatalogTestWithItsUnit(LabTest test, String unit) {
        var row = new LabResult(UUID.fromString("22222222-2222-4222-8222-222222222222"), "SYN-001", "LAB-001", test,
                new BigDecimal("5.4000"), test.unit(), Instant.parse("2026-01-15T10:30:00Z"), "FINAL", 1,
                Instant.parse("2026-01-15T11:00:00Z"));
        String[] cells = csv.export(List.of(row)).split("\r\n")[1].split(",");
        assertThat(cells[3]).isEqualTo(test.name());
        assertThat(cells[4]).isEqualTo("5.4000");
        assertThat(cells[5]).isEqualTo(unit);
    }

    @Test void quotesFieldsThatContainCommasQuotesOrLineBreaks() {
        assertThat(ResultCsv.cell("plain")).isEqualTo("plain");
        assertThat(ResultCsv.cell("a,b")).isEqualTo("\"a,b\"");
        assertThat(ResultCsv.cell("say \"hi\"")).isEqualTo("\"say \"\"hi\"\"\"");
        assertThat(ResultCsv.cell("line\nbreak")).isEqualTo("\"line\nbreak\"");
    }
}
