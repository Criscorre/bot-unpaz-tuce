/**
 * whatsapp_bridge.js — Bot TUCE WhatsApp
 * La sesión de WhatsApp se persiste en Firebase para sobrevivir redeploys.
 * Para vincular por primera vez: abrí /qr en el navegador del celu.
 */

const {
    default: makeWASocket,
    useMultiFileAuthState,
    DisconnectReason,
    fetchLatestBaileysVersion,
} = require("@whiskeysockets/baileys");
const axios   = require("axios");
const pino    = require("pino");
const QRCode  = require("qrcode");
const http    = require("http");
const fs      = require("fs");
const admin   = require("firebase-admin");

const WEBHOOK_URL = process.env.WEBHOOK_URL || "http://localhost:5000/wa";
const PORT        = process.env.PORT || 3000;
const SESSION_DIR = "auth_info_baileys";
const FB_SESSION_KEY = "wa_session";

// ─── Firebase Admin ───────────────────────────────────────────────────────────
const firebaseJson = process.env.FIREBASE_JSON;
const firebaseUrl  = process.env.FIREBASE_DB_URL;

let fbDb = null;
if (firebaseJson && firebaseUrl) {
    try {
        admin.initializeApp({
            credential:  admin.credential.cert(JSON.parse(firebaseJson)),
            databaseURL: firebaseUrl,
        });
        fbDb = admin.database();
        console.log("✅ Firebase conectado (Node.js)");
    } catch (e) {
        console.error("❌ Error Firebase:", e.message);
    }
}

// ─── Persistencia de sesión en Firebase ──────────────────────────────────────

// Firebase no acepta "." en las claves → lo escapamos
const escKey   = (k) => k.replace(/\./g, "___DOT___");
const unescKey = (k) => k.replace(/___DOT___/g, ".");

async function downloadSession() {
    if (!fbDb) return false;
    try {
        const snap = await fbDb.ref(FB_SESSION_KEY).once("value");
        if (!snap.exists()) return false;
        const data = snap.val();
        if (!fs.existsSync(SESSION_DIR)) fs.mkdirSync(SESSION_DIR, { recursive: true });
        for (const [escapedName, content] of Object.entries(data)) {
            fs.writeFileSync(`${SESSION_DIR}/${unescKey(escapedName)}`, content, "utf-8");
        }
        console.log(`✅ Sesión WA restaurada (${Object.keys(data).length} archivos)`);
        return true;
    } catch (e) {
        console.error("❌ Error restaurando sesión:", e.message);
        return false;
    }
}

async function uploadSession() {
    if (!fbDb) return;
    try {
        if (!fs.existsSync(SESSION_DIR)) return;
        const files = fs.readdirSync(SESSION_DIR);
        if (!files.length) return;
        const data = {};
        for (const file of files) {
            data[escKey(file)] = fs.readFileSync(`${SESSION_DIR}/${file}`, "utf-8");
        }
        await fbDb.ref(FB_SESSION_KEY).set(data);
        console.log(`💾 Sesión WA guardada en Firebase (${files.length} archivos)`);
    } catch (e) {
        console.error("❌ Error guardando sesión:", e.message);
    }
}

// ─── QR en memoria ────────────────────────────────────────────────────────────
let qrDataUrl = null;

// ─── Servidor HTTP ────────────────────────────────────────────────────────────
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
                <p style="color:#333;margin-top:16px">WhatsApp → <b>Dispositivos vinculados</b> → <b>Vincular dispositivo</b></p>
                <p style="color:#999;font-size:12px">El QR expira en ~60 seg. Esta página se actualiza sola.</p>
                <script>setTimeout(()=>location.reload(), 20000)</script>
            </body></html>`);
        }
    } else {
        res.writeHead(200);
        res.end("OK");
    }
}).listen(PORT, () =>
    console.log(`🌍 Servidor activo en puerto ${PORT} — QR en /qr`)
);

// ─── Bot WhatsApp ─────────────────────────────────────────────────────────────
async function startBot() {
    // Restaurar sesión desde Firebase antes de arrancar Baileys
    await downloadSession();

    const { state, saveCreds } = await useMultiFileAuthState(SESSION_DIR);
    const { version }          = await fetchLatestBaileysVersion();

    const sock = makeWASocket({
        version,
        auth:    state,
        logger:  pino({ level: "silent" }),
        browser: ["Bot TUCE", "Chrome", "1.0"],
    });

    // Guardar credenciales localmente Y en Firebase
    sock.ev.on("creds.update", async () => {
        await saveCreds();
        await uploadSession();
    });

    sock.ev.on("connection.update", async ({ connection, lastDisconnect, qr }) => {
        if (qr) {
            try {
                qrDataUrl = await QRCode.toDataURL(qr, { width: 300, margin: 2 });
                console.log("📱 QR listo — abrí /qr en tu navegador para escanearlo");
            } catch (e) {
                console.error("Error generando QR:", e.message);
            }
        }
        if (connection === "open") {
            qrDataUrl = null;
            console.log("✅ WhatsApp conectado — Bot TUCE activo");
            await uploadSession(); // Guardar sesión completa al conectar
        }
        if (connection === "close") {
            const code = lastDisconnect?.error?.output?.statusCode;
            if (code === DisconnectReason.loggedOut) {
                console.log("❌ Sesión cerrada. Limpiando y reconectando...");
                if (fbDb) await fbDb.ref(FB_SESSION_KEY).remove();
                if (fs.existsSync(SESSION_DIR)) fs.rmSync(SESSION_DIR, { recursive: true });
                setTimeout(() => startBot(), 5000);
            } else {
                // Backoff: esperar antes de reconectar para no saturar
                const delay = 5000 + Math.random() * 5000;
                console.log(`🔄 Reconectando en ${Math.round(delay/1000)}s...`);
                setTimeout(() => startBot(), delay);
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

            // Reintentar POST al Flask hasta 3 veces con espera entre intentos
            let respuesta = null;
            for (let intento = 1; intento <= 3; intento++) {
                try {
                    const res = await axios.post(
                        WEBHOOK_URL,
                        { from, message: text },
                        { timeout: 25000 }
                    );
                    respuesta = res.data?.response;
                    break;
                } catch (err) {
                    console.error(`❌ Error webhook (intento ${intento}/3):`, err.message);
                    if (intento < 3) await new Promise(r => setTimeout(r, 3000 * intento));
                }
            }
            if (respuesta) {
                await sock.sendMessage(from, { text: respuesta });
            } else {
                await sock.sendMessage(from, {
                    text: "⚠️ El servicio está iniciando. Intentá de nuevo en 30 segundos.",
                });
            }
        }
    });
}

startBot().catch(console.error);
