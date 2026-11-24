import type { Metadata } from "next";
import "../src/styles.css";
import "./workspace.css";
export const metadata: Metadata = {
  title: "AllocateAI · Evidence to opportunity",
  description:
    "Independent academic internship recommendations and reviewed allocation, with an auditable agent workflow.",
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
