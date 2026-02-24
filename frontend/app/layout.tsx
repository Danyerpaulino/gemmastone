import "./globals.css";

import { IBM_Plex_Sans, Space_Grotesk } from "next/font/google";

import DemoGate from "@/components/DemoGate";

const bodyFont = IBM_Plex_Sans({
    subsets: ["latin"],
    weight: ["300", "400", "500", "600", "700"],
    variable: "--font-body",
});

const displayFont = Space_Grotesk({
    subsets: ["latin"],
    weight: ["400", "500", "600", "700"],
    variable: "--font-display",
});

export const metadata = {
    title: "GemmaStone",
    description: "Voice-first kidney stone prevention platform.",
};

export default function RootLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <html lang="en">
            <body className={`${bodyFont.variable} ${displayFont.variable}`}>
                <DemoGate>{children}</DemoGate>
            </body>
        </html>
    );
}
