import type { FormatCapability } from "../types";

interface FormatSelectProps {
  formats: FormatCapability[];
  value: string;
  direction: "input" | "output";
  onChange: (value: string) => void;
}

export function FormatSelect({
  formats,
  value,
  direction,
  onChange,
}: FormatSelectProps) {
  const visibleFormats = formats.filter((format) =>
    direction === "input" ? format.can_read : format.can_write,
  );
  const groups = visibleFormats.reduce(
    (result, format) => {
      const group = result.get(format.family);
      if (group) {
        group.push(format);
      } else {
        result.set(format.family, [format]);
      }
      return result;
    },
    new Map<string, FormatCapability[]>(),
  );

  return (
    <label className="field">
      <span>{direction === "input" ? "Source format" : "Destination format"}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">Select a format</option>
        {Array.from(groups, ([family, items]) => (
          <optgroup label={family} key={family}>
            {items.map((format) => (
              <option value={format.id} key={format.id}>
                {format.label}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
    </label>
  );
}
