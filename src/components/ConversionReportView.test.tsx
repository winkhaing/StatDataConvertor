import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ConversionResult } from "../types";
import { ConversionReportView } from "./ConversionReportView";

describe("ConversionReportView", () => {
  it("shows structured temporal transformations", () => {
    const result: ConversionResult = {
      output_path: "/tmp/output.dta",
      report_path: "/tmp/output.dta.statdata-report.json",
      report: {
        input_path: "/tmp/input.xlsx",
        output_path: "/tmp/output.dta",
        input_format: "excel_xlsx",
        output_format: "stata",
        started_at: "2026-07-29T00:00:00Z",
        finished_at: "2026-07-29T00:00:01Z",
        status: "completed",
        rows: 2,
        columns: 1,
        changes: [
          {
            severity: "warning",
            code: "temporal.datetime_reduced",
            message: "Fractional-second precision was removed.",
            columns: ["observed"],
          },
        ],
        temporal: [
          {
            column: "observed",
            source_kind: "datetime",
            source_precision: "microsecond",
            source_timezone: "UTC",
            destination_kind: "datetime",
            destination_precision: "second",
            destination_timezone: null,
            outcome: "lossy",
            code: "temporal.datetime_reduced",
            message:
              "The destination writer removes fractional-second precision and timezone information.",
          },
        ],
        lossless: false,
        summary: {
          info: 0,
          warning: 1,
          error: 0,
          temporal_columns: 1,
          temporal_lossy: 1,
        },
      },
    };

    const { container } = render(
      <ConversionReportView result={result} onReset={vi.fn()} />,
    );

    expect(
      screen.getByRole("heading", { name: "Temporal columns checked" }),
    ).toBeInTheDocument();
    expect(screen.getByText("1 of 1 changed")).toBeInTheDocument();
    expect(screen.getByText("observed")).toBeInTheDocument();
    expect(container.querySelector(".temporal-route")).toHaveTextContent(
      "datetime · microsecond · UTC → datetime · second",
    );
  });
});
