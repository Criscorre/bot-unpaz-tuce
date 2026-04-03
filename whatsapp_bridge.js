/**
 * whatsapp_bridge.js — Bot TUCE WhatsApp
 * Usa Baileys para conectarse a WhatsApp Web y reenvía
 * cada mensaje al webhook Python (Flask) en puerto 5000.
 *
 * Para vincular el número: abrí https://[tu-url-koyeb]/qr desde el celu
 * y escaneá la imagen con WhatsApp → Dispositivos vinculados → Vincular dispositivo.
 * La sesión se guarda en ./auth_info_baileys y no hay que volver a escanear.
 */

const {
    default: makeWASocket,
    useMultiFileAuthState,
    DisconnectReason,
    fetchLatestBaileysVersion,
} = require("@whiskeysockets/baileys");
const axios  = require("axios");
const pino   = require("pino");
const QRCode = require("qrcode");
const http   = require("http");

const WEBHOOK_URL = process.env.WEBHOOK_URL || "http://localhost:5000/wa";
const PORT        = process.env.PORT || 3000;

// QR actual en memoria (se actualiza cada vez que Baileys genera uno nuevo)
let qrDataUrl = null;

// ─── Servidor HTTP ────────────────────────────────────────────────────────────
// GET /     → health check para Koyeb
// GET /qr   → página con imagen del QR para escanear desde el celu
http.createServer(async (req, res) => {
    if (req.url === "/qr") {
        if (!qrDataUrl) {
            res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
            res.end(`<!DOCTYPE html><html><body style="font-family:sans-serif;text-align:center;padding:40px">
                <h2>⏳ Generando QR...</h2>
                <p>Esperá unos segundos y recargá la página.</p>
                <script>setTimeout(()=>location.reload(), 3000)</script>
            </body></html>`);
        } else {
            res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
            res.end(`<!DOCTYPE html><html><body style="font-family:sans-serif;text-align:center;padding:40px;background:#f0f0f0">
                <h2 style="color:#128C7E">📱 Vinculá tu WhatsApp</h2>
                <img src="${qrDataUrl}" style="width:280px;height:280px;border:5px solid #25D366;border-radius:16px;background:#fff;padding:10px">
                <p style="color:#333;margin-top:16px">Abrí WhatsApp → <b>Dispositivos vinculados</b> → <b>Vincular dispositivo</b></p>
                <p style="color:#999;font-size:12px">El QR expira en ~60 seg. Esta página se actualiza sola.</p>
                <script>setTimeout(()=>location.reload(), 20000)</script>
            </body></html>`);
        }
    } else {
        res.writeHead(200);
        res.end("OK");
    }
}).listen(PORT, () =>
    console.log(`🌍 Servidor activo en puerto ${PORT} — QR disponible en /qr`)
);

// ─── Bot WhatsApp ─────────────────────────────────────────────────────────────
async function startBot() {
    const { state, saveCreds } = await useMultiFileAuthState("auth_info_baileys");
    const { version }          = await fetchLatestBaileysVersion();

    const sock = makeWASocket({
        version,
        auth:    state,
        logger:  pino({ level: "silent" }),
        browser: ["Bot TUCE", "Chrome", "1.0"],
    });

    sock.ev.on("creds.update", saveCreds);

    sock.ev.on("connection.update", async ({ connection, lastDisconnect, qr }) => {
        if (qr) {
            // Guardar QR como imagen base64 para servirla en /qr
            try {
                qrDataUrl = await QRCode.toDataURL(qr, { width: 300, margin: 2 });
                console.log("📱 QR listo — abrí /qr en tu navegador para escanearlo");
            } catch (e) {
                console.error("Error generando QR:", e.message);
            }
        }
        if (connection === "open") {
            qrDataUrl = null; // limpiar QR una vez conectado
            console.log("✅ WhatsApp conectado — Bot TUCE activo");
        }
        if (connection === "close") {
            const code = lastDisconnect?.error?.output?.statusCode;
            if (code !== DisconnectReason.loggedOut) {
                console.log("🔄 Reconectando...");
                startBot();
            } else {
                console.log("❌ Sesión cerrada. Borrá auth_info_baileys y reiniciá.");
            }
        }
    });

    sock.ev.on("messages.upsert", async ({ messages, type }) => {
        if (type !== "notify") return;

        for (const msg of messages) {
            if (msg.key.fromMe)                           continue;
            if (msg.key.remoteJid.endsWith("@g.us"))      continue;
            if (!msg.message)                             continue;

            const from = msg.key.remoteJid;
            const text = (
                msg.message.conversation ||
                msg.message.extendedTextMessage?.text ||
                ""
            ).trim();

            if (!text) continue;

            console.log(`📩 ${from}: ${text}`);

            try {
                const res = await axios.post(
                    WEBHOOK_URL,
                    { from, message: text },
                    { timeout: 20000 }
                );
                const respuesta = res.data?.response || "⚠️ Sin respuesta";
                await sock.sendMessage(from, { text: respuesta });
            } catch (err) {
                console.error("❌ Error webhook:", err.message);
                await sock.sendMessage(from, {
                    text: "⚠️ Tuve un problema. Intentá de nuevo en un momento.",
                });
            }
        }
    });
}

startBot().catch(console.error);
