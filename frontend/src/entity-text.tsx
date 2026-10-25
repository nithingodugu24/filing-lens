import { highlightRange } from "./text-highlights";
export type PageEntity = {
  id: string;
  text: string;
  type: string;
  mentions: { start: number; end: number; page_index: number }[];
};
const colors: Record<string, string> = {
  COMPANY: "#4779cf",
  PERSON: "#168264",
  MONEY: "#b97a20",
  METRIC: "#9b5fc0",
  DATE: "#66758c",
  PERCENTAGE: "#d16f42",
};
export function EntityText({
  text,
  quote,
  entities,
}: {
  text: string;
  quote: string;
  entities: PageEntity[];
}) {
  const match = highlightRange(text, quote);
  const ranges = entities
    .flatMap((e) =>
      e.mentions.map((m) => ({ ...m, type: e.type, name: e.text })),
    )
    .filter((r) => r.start >= 0 && r.end <= text.length);
  const boundaries = [
    ...new Set([
      0,
      text.length,
      ...ranges.flatMap((r) => [r.start, r.end]),
      ...(match ?? []),
    ]),
  ].sort((a, b) => a - b);
  return (
    <>
      {boundaries.slice(0, -1).map((start, i) => {
        const end = boundaries[i + 1],
          entity = ranges.find((r) => r.start <= start && r.end >= end),
          highlight = match && start >= match[0] && end <= match[1];
        const span = (
          <span
            title={entity ? `${entity.type}: ${entity.name}` : undefined}
            style={
              entity
                ? {
                    textDecorationLine: "underline",
                    textDecorationColor: colors[entity.type],
                    textDecorationThickness: 2,
                    textUnderlineOffset: 3,
                  }
                : undefined
            }
          >
            {text.slice(start, end)}
          </span>
        );
        return highlight ? (
          <mark key={start}>{span}</mark>
        ) : (
          <span key={start}>{span}</span>
        );
      })}
    </>
  );
}
