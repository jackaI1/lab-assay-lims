import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "Clinic intake | Practice queue",
  description:
    "A fictional clinic intake queue with anonymous practice tickets. No real patient data.",
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <a className="skip-link" href="#main">
          Skip to intake queue
        </a>
        {children}
      </body>
    </html>
  );
}
