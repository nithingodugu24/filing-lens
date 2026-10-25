export function HighlightText({
  text,
  quote,
}: {
  text: string;
  quote: string;
}) {
  const parts = highlightRange(text, quote);
  return parts ? (
    <>
      {text.slice(0, parts[0])}
      <mark>{text.slice(parts[0], parts[1])}</mark>
      {text.slice(parts[1])}
    </>
  ) : (
    <>{text}</>
  );
}
export function highlightRange(
  text: string,
  quote: string,
): [number, number] | null {
  if (!quote.trim()) return null;
  const positions: number[] = [];
  let normal = "";
  let space = false;
  for (let i = 0; i < text.length; i++) {
    if (/[\s|]/.test(text[i])) {
      if (!space) {
        normal += " ";
        positions.push(i);
      }
      space = true;
    } else {
      normal += text[i];
      positions.push(i);
      space = false;
    }
  }
  const match = normal.toLowerCase().indexOf(
    quote
      .replace(/[\s|]+/g, " ")
      .trim()
      .toLowerCase(),
  );
  return match < 0
    ? null
    : [
        positions[match],
        positions[match + quote.replace(/[\s|]+/g, " ").trim().length - 1] + 1,
      ];
}
