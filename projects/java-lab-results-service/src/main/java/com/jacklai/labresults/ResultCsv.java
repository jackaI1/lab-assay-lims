package com.jacklai.labresults;

import java.util.List;

/**
 * Writes results as RFC 4180 CSV (comma-separated text with CRLF line endings) so a lab
 * spreadsheet program can open the export directly. Quoting protects any field that
 * contains a comma, quote or line break.
 */
final class ResultCsv {
    static final String HEADER = "id,patient_id,specimen_id,test,value,unit,observed_at,status,revision,updated_at";

    String export(List<LabResult> results) {
        var csv = new StringBuilder(HEADER).append("\r\n");
        for (LabResult result : results) {
            csv.append(row(result)).append("\r\n");
        }
        return csv.toString();
    }

    private static String row(LabResult result) {
        return String.join(",",
                cell(result.id().toString()),
                cell(result.patientId()),
                cell(result.specimenId()),
                cell(result.test().name()),
                // Plain notation keeps values such as 0.0001 out of scientific form.
                cell(result.value().toPlainString()),
                cell(result.unit()),
                cell(result.observedAt().toString()),
                cell(result.status()),
                cell(String.valueOf(result.revision())),
                cell(result.updatedAt().toString()));
    }

    static String cell(String value) {
        if (value.indexOf(',') < 0 && value.indexOf('"') < 0 && value.indexOf('\n') < 0 && value.indexOf('\r') < 0) {
            return value;
        }
        return "\"" + value.replace("\"", "\"\"") + "\"";
    }
}
