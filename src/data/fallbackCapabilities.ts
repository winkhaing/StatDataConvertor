import type {
  CapabilityResponse,
  DirectionCertification,
  FormatCapability,
} from "../types";

const format = (
  value: Omit<
    FormatCapability,
    "availability" | "requires" | "trust"
  > &
    Partial<
      Pick<FormatCapability, "availability" | "requires" | "trust">
    >,
): FormatCapability => ({
  availability: "available",
  requires: [],
  trust: "experimental",
  ...value,
});

const pendingDetail =
  "Awaiting independently generated vendor fixtures, a successful destination-opening check, and maintainer review.";

const pendingCertification = (
  detail = pendingDetail,
): DirectionCertification => ({
  state: "pending",
  certified: false,
  tested_versions: [],
  evidence_count: 0,
  detail,
});

const fixtureCertification = (
  tested_versions: string[],
  evidence_count: number,
  detail: string,
): DirectionCertification => ({
  state: "fixture_tested",
  certified: false,
  tested_versions,
  evidence_count,
  detail,
});

export const fallbackCapabilities: CapabilityResponse = {
  engine_version: "0.10.0",
  python_version: "bundled",
  privacy: { local_only: true, network_access: false },
  bridges: [],
  vendor_runtimes: [],
  certifications: [
    {
      format_id: "jmp",
      family: "JMP",
      label: "JMP data table",
      read: fixtureCertification(
        ["17.2", "18.2.1"],
        2,
        "The open reader has native JMP fixtures, but this is not a vendor certification.",
      ),
      write: pendingCertification(),
    },
    {
      format_id: "sas_data",
      family: "SAS",
      label: "SAS data file",
      read: pendingCertification(),
      write: pendingCertification(),
    },
    {
      format_id: "sas_cport",
      family: "SAS",
      label: "SAS CPORT",
      read: pendingCertification(),
      write: pendingCertification(),
    },
    {
      format_id: "sas_catalog",
      family: "SAS",
      label: "SAS format catalog",
      read: pendingCertification(
        "Catalog evidence must be paired with its data set and a licensed SAS runtime.",
      ),
      write: pendingCertification(
        "Catalog evidence must be paired with its data set and a licensed SAS runtime.",
      ),
    },
    {
      format_id: "minitab",
      family: "Minitab",
      label: "Modern Minitab worksheet / project",
      read: pendingCertification(),
      write: pendingCertification(),
    },
    {
      format_id: "statistica",
      family: "Statistica",
      label: "Statistica data file",
      read: pendingCertification(),
      write: pendingCertification(),
    },
    {
      format_id: "eviews_wf1",
      family: "EViews",
      label: "EViews binary workfile",
      read: fixtureCertification(
        [],
        1,
        "Vendor-published workfiles have been exercised, but the evidence is not yet a redistributable certification set.",
      ),
      write: pendingCertification(
        "Binary WF1 writing is not implemented in the open core.",
      ),
    },
    {
      format_id: "eviews_wf2",
      family: "EViews",
      label: "EViews open workfile",
      read: fixtureCertification(
        [],
        1,
        "Automated open-format fixtures pass; vendor-release opening evidence is still pending.",
      ),
      write: fixtureCertification(
        [],
        1,
        "Automated round trips pass; opening app-written files in supported EViews releases is still pending.",
      ),
    },
  ],
  formats: [
    format({
      id: "csv",
      family: "CSV",
      label: "CSV / delimited text",
      extensions: [".csv", ".tsv"],
      can_read: true,
      can_write: true,
      trust: "verified",
      detail: "UTF-8 CSV and TSV with configurable delimiter and encoding.",
    }),
    format({
      id: "excel_xlsx",
      family: "Excel",
      label: "Excel workbook",
      extensions: [".xlsx"],
      can_read: true,
      can_write: true,
      trust: "verified",
      detail: "Modern Excel workbooks; one selected worksheet per conversion.",
    }),
    format({
      id: "excel_xls",
      family: "Excel",
      label: "Legacy Excel workbook",
      extensions: [".xls"],
      can_read: true,
      can_write: false,
      detail: "Reads one worksheet from historical Excel .xls workbooks.",
      requires: ["xlrd"],
    }),
    format({
      id: "jsonstat",
      family: "JSON-stat",
      label: "JSON-stat dataset",
      extensions: [".json", ".jsonstat"],
      can_read: true,
      can_write: true,
      detail: "Reads v1/v2 datasets and writes JSON-stat 2.0.",
    }),
    format({
      id: "sas_data",
      family: "SAS",
      label: "SAS data file",
      extensions: [".sas7bdat"],
      can_read: true,
      can_write: false,
      detail: "Native SAS data is read-only in the open core.",
      requires: ["pyreadstat"],
    }),
    format({
      id: "sas_xport",
      family: "SAS",
      label: "SAS XPORT",
      extensions: [".xpt"],
      can_read: true,
      can_write: true,
      detail: "SAS transport v5 and v8.",
      requires: ["pyreadstat"],
    }),
    format({
      id: "sas_catalog",
      family: "SAS",
      label: "SAS format catalog",
      extensions: [".sas7bcat"],
      can_read: false,
      can_write: false,
      availability: "vendor_bridge",
      trust: "planned",
      detail:
        "Catalog conversion requires association with a dataset or a SAS bridge.",
    }),
    format({
      id: "sas_cport",
      family: "SAS",
      label: "SAS CPORT",
      extensions: [".cpo", ".cport"],
      can_read: false,
      can_write: false,
      availability: "vendor_bridge",
      trust: "planned",
      detail: "A local SAS Foundation batch bridge is required.",
    }),
    format({
      id: "sas_program",
      family: "SAS",
      label: "SAS program + CSV data",
      extensions: [".sas"],
      can_read: false,
      can_write: true,
      detail:
        "Writes a portable SAS DATA-step program plus a UTF-8 CSV sidecar.",
    }),
    format({
      id: "spss_data",
      family: "IBM SPSS",
      label: "SPSS data file",
      extensions: [".sav", ".zsav"],
      can_read: true,
      can_write: true,
      detail: "Compressed and uncompressed SPSS system files.",
      requires: ["pyreadstat"],
    }),
    format({
      id: "spss_portable",
      family: "IBM SPSS",
      label: "SPSS portable file",
      extensions: [".por"],
      can_read: true,
      can_write: false,
      detail: "Portable files are read-only in the open core.",
      requires: ["pyreadstat"],
    }),
    format({
      id: "stata",
      family: "Stata",
      label: "Stata data file",
      extensions: [".dta"],
      can_read: true,
      can_write: true,
      detail: "All ReadStat-supported generations.",
      requires: ["pyreadstat"],
    }),
    format({
      id: "jmp",
      family: "JMP",
      label: "JMP data table",
      extensions: [".jmp"],
      can_read: true,
      can_write: false,
      detail:
        "License-free native JMP reading is built in. Native JMP writing is not yet available.",
    }),
    format({
      id: "r_data",
      family: "R",
      label: "R data object / workspace",
      extensions: [".rds", ".rdata", ".rda"],
      can_read: true,
      can_write: true,
      detail:
        "Bundled, local RDS and R workspace reader/writer; no R installation is required.",
      requires: ["rdata"],
    }),
    format({
      id: "minitab_portable",
      family: "Minitab",
      label: "Minitab Portable Worksheet",
      extensions: [".mtp"],
      can_read: true,
      can_write: false,
      detail:
        "Reads legacy text-based MTP worksheets through local R and its recommended foreign package.",
      requires: ["Rscript", "R package: foreign"],
    }),
    format({
      id: "eviews_wf2",
      family: "EViews",
      label: "EViews open workfile",
      extensions: [".wf2"],
      can_read: true,
      can_write: true,
      detail:
        "Reads and writes open WF2 JSON/gzip without requiring EViews.",
    }),
    format({
      id: "eviews_wf1",
      family: "EViews",
      label: "EViews binary workfile",
      extensions: [".wf1"],
      can_read: true,
      can_write: false,
      detail:
        "Reads legacy binary WF1 workfiles without requiring EViews.",
    }),
    ...[
      [
        "minitab",
        "Minitab",
        "Modern Minitab worksheet / project",
        [".mtw", ".mwx", ".mpj", ".mpx"],
      ],
      ["statistica", "Statistica", "Statistica data file", [".sta"]],
    ].map(([id, family, label, extensions]) =>
      format({
        id: id as string,
        family: family as string,
        label: label as string,
        extensions: extensions as string[],
        can_read: false,
        can_write: false,
        availability: "vendor_bridge",
        trust: "planned",
        detail:
          id === "statistica"
            ? "No maintained open STA parser has been independently verified; a local vendor bridge is required."
            : "An optional local vendor bridge is required.",
      }),
    ),
  ],
};
