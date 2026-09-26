import type { Metadata } from "next";
import "./globals.css";
import "./auth.css";
import Providers from "./providers";

export const metadata: Metadata = {
  title: "ADDA AI - Agent workspace",
  description: "A multi-agent workspace that shows the route, the evidence, and the result.",
};

const appearanceScript = `(()=>{const d=document.documentElement;let m="adaptive",a="ocean";try{const r=localStorage.getItem("adda-appearance");if(r){const p=JSON.parse(r);if(["adaptive","light","dark"].includes(p.mode))m=p.mode;if(["ocean","forest","violet","amber","graphite"].includes(p.accent))a=p.accent}else{const l=localStorage.getItem("adda-theme");if(l==="light"||l==="dark")m=l}}catch{}const t=m==="adaptive"?(matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light"):m;d.dataset.theme=t;d.dataset.appearance=m;d.dataset.accent=a})()`;

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head><script dangerouslySetInnerHTML={{ __html: appearanceScript }} /></head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
