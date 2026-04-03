/**
 * whatsapp_bridge.js — Bot TUCE WhatsApp
 * Usa Baileys para conectarse a WhatsApp Web y reenvía
 * cada mensaje al webhook Python (Flask) en puerto 5000.
 *
 * Primera vez: escanear QR en la terminal de Koyeb.
 * La sesión se guarda en ./auth_info_baileys y no hay que volver a escanear.
 */

const {
    default: makeWASocket,
    useMultiFileAuthState,
    DisconnectReason,
    fetchLatestBaileysVersion,
} = require("@whiskeysockets/baileys");
const axios   = require("axios");
const pino    = require("pino");
const qrcode  = require("qrcode-terminal");

const WEBHOOK_URL = process.env.WEBHOOK_URL || "http://localhost:5000/wa";
const PORT        = process.env.PORT || 3000;

// ─── Servidor de health check para Koyeb ─────────────────────────────────────
const http = require("http");
http.createServer((_, res) => res.end("OK")).listen(PORT, () =>
    console.log(`🌍 Health server activo en puerto ${PORT}`)
);

// ─── Bot WhatsApp ─────────────────────────────────────────────────────────────
async function startBot() {
    const { state, saveCreds } = await useMultiFileAuthState("auth_info_baileys");
    const { version }          = await fetchLatestBaileysVersion();

    const sock = makeWASocket({
        version,
        auth:   state,
        logger: pino({ level: "silent" }),
        browser: ["Bot TUCE", "Chrome", "1.0"],
    });

    // Guardar credenciales cuando cambian
    sock.ev.on("creds.update", saveCreds);

    // Manejo de conexión / desconexión
    sock.ev.on("connection.update", ({ connection, lastDisconnect, qr }) => {
        if (qr) {
            // Dibujar QR en la terminal (compatible con logs de Koyeb)
            qrcode.generate(qr, { small: true });
            console.log("📱 Escaneá el QR de arriba con tu WhatsApp secundario");
        }
        if (connection === "open") {
            console.log("✅ WhatsApp conectado — Bot TUCE activo");
        }
        if (connection === "close") {
            const code = lastDisconnect?.error?.output?.statusCode;
            if (code !== DisconnectReason.loggedOut) {
                console.log("🔄 Reconectando...");
                startBot();
            } else {
                console.log("❌ Sesión cerrada. Borrá la carpeta auth_info_baileys y reiniciá.");
            }
        }
    });

    // Procesar mensajes entrantes
    sock.ev.on("messages.upsert", async ({ messages, type }) => {
        if (type !== "notify") return;

        for (const msg of messages) {
            // Ignorar mensajes propios, de grupos y sin texto
            if (msg.key.fromMe)                                      continue;
            if (msg.key.remoteJid.endsWith("@g.us"))                 continue;
            if (!msg.message)                                        continue;

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
