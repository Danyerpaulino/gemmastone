import "./globals.css";

import DemoGate from "@/components/DemoGate";

export const metadata = {
    title: "KidneyStone AI",
    description: "Provider portal",
};

export default function RootLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <html lang="en">
            <body>
                <DemoGate>{children}</DemoGate>
            </body>
        </html>
    );
}
