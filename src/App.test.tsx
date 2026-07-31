import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "./App";

describe("StatData Converter app", () => {
  it("shows the local conversion workflow", async () => {
    render(<App />);

    expect(
      screen.getByRole("heading", {
        name: /move data between tools/i,
      }),
    ).toBeInTheDocument();
    expect(screen.getByText(/100% local processing/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /convert dataset/i }),
    ).toBeDisabled();
    expect(
      screen.getByRole("combobox", { name: /date & time handling/i }),
    ).toHaveValue("safe");
  });

  it("shows directional format support", async () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "Formats" }));

    expect(
      screen.getByRole("heading", { name: /know exactly what will convert/i }),
    ).toBeInTheDocument();
    expect(screen.getByText("JMP data table")).toBeInTheDocument();
    expect(screen.getByText("R data object / workspace")).toBeInTheDocument();
    expect(screen.getByText("Minitab Portable Worksheet")).toBeInTheDocument();
    expect(screen.getByText("EViews open workfile")).toBeInTheDocument();
    expect(screen.getByText("EViews binary workfile")).toBeInTheDocument();
    expect(screen.getAllByText("Vendor bridge").length).toBeGreaterThan(0);
  });

  it("exposes evidence-based round-trip validation", () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "Validate" }));

    expect(
      screen.getByRole("heading", {
        name: /test a round trip before you trust a format/i,
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /run round-trip test/i }),
    ).toBeDisabled();
  });

  it("shows local vendor bridge management", () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "Vendor bridges" }));

    expect(
      screen.getByRole("heading", {
        name: /connect trusted software already on this computer/i,
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /add local bridge/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /audit evidence package/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/local runtime checks/i)).toBeInTheDocument();
  });
});
