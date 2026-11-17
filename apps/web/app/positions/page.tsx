import { redirect } from "next/navigation";

/** /positions has no page of its own; start at goalkeepers, the first group. */
export default function PositionsIndex() {
  redirect("/positions/gk");
}
