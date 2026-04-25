/**
 * whatsapp_bridge.js — Bot TUCE WhatsApp + Sistema de Alertas Bytes Creativos
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

const WEBHOOK_URL       = process.env.WEBHOOK_URL       || "http://localhost:5000/wa";
const PORT              = process.env.PORT              || 3000;
const META_VERIFY_TOKEN = process.env.META_VERIFY_TOKEN || "bytes2024";
const GRUPO_INTERNO_JID = process.env.GRUPO_INTERNO_JID || "";
const META_ACCESS_TOKEN = process.env.META_ACCESS_TOKEN || "";
const SESSION_DIR       = "auth_info_baileys";
const FB_SESSION_KEY    = "wa_session";

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

// ─── Sistema de alertas Bytes Creativos ──────────────────────────────────────
let sockGlobal = null; // referencia al socket activo

async function sendGroupAlert(text) {
    if (!sockGlobal) {
        console.warn("⚠️ Alerta pendiente: bot no conectado aún");
        return false;
    }
    if (!GRUPO_INTERNO_JID) {
        console.warn("⚠️ GRUPO_INTERNO_JID no configurado en variables de entorno");
        return false;
    }
    try {
        await sockGlobal.sendMessage(GRUPO_INTERNO_JID, { text });
        console.log("✅ Alerta enviada al grupo interno");
        return true;
    } catch (e) {
        console.error("❌ Error enviando alerta al grupo:", e.message);
        return false;
    }
}

function formatHora(timestampMs) {
    return new Date(timestampMs).toLocaleString("es-AR", {
        timeZone: "America/Argentina/Buenos_Aires",
        hour:     "2-digit",
        minute:   "2-digit",
        day:      "2-digit",
        month:    "2-digit",
    });
}

async function getNombreMeta(senderId) {
    if (!META_ACCESS_TOKEN) return senderId;
    try {
        const r = await axios.get(`https://graph.facebook.com/v19.0/${senderId}`, {
            params: { fields: "name", access_token: META_ACCESS_TOKEN },
            timeout: 5000,
        });
        return r.data?.name || senderId;
    } catch (_) {
        return senderId;
    }
}

async function procesarMetaWebhook(body) {
    const obj = body.object;

    // ── Instagram DM ──
    if (obj === "instagram") {
        const msg = body.entry?.[0]?.messaging?.[0];
        if (!msg?.message || msg.message.is_echo) return;
        const nombre = await getNombreMeta(msg.sender.id);
        const texto  = msg.message.text || "[Adjunto/Sticker]";
        const hora   = formatHora(msg.timestamp * 1000);
        await sendGroupAlert(
            `🔔 *NUEVO MENSAJE — Bytes Creativos*\n\n` +
            `📸 *Instagram DM*\n` +
            `👤 *De:* ${nombre}\n` +
            `💬 *Mensaje:* ${texto}\n` +
            `🕐 *Hora:* ${hora}\n\n` +
            `🔗 https://www.instagram.com/direct/inbox/`
        );
        return;
    }

    // ── Messenger ──
    if (obj === "page") {
        const msg = body.entry?.[0]?.messaging?.[0];
        if (!msg?.message || msg.message.is_echo) return;
        const nombre = await getNombreMeta(msg.sender.id);
        const texto  = msg.message.text || "[Adjunto]";
        const hora   = formatHora(msg.timestamp);
        await sendGroupAlert(
            `🔔 *NUEVO MENSAJE — Bytes Creativos*\n\n` +
            `💬 *Messenger*\n` +
            `👤 *De:* ${nombre}\n` +
            `💬 *Mensaje:* ${texto}\n` +
            `🕐 *Hora:* ${hora}\n\n` +
            `🔗 https://business.facebook.com/latest/inbox/all`
        );
        return;
    }

    // ── WhatsApp Business API ──
    if (obj === "whatsapp_business_account") {
        const change = body.entry?.[0]?.changes?.[0];
        if (change?.field !== "messages") return;
        const value = change.value;
        const msg   = value?.messages?.[0];
        if (!msg || msg.type === "reaction") return;
        const nombre = value.contacts?.[0]?.profile?.name || `+${msg.from}`;
        const texto  = msg.text?.body || `[${msg.type}]`;
        const hora   = formatHora(parseInt(msg.timestamp) * 1000);
        await sendGroupAlert(
            `🔔 *NUEVO MENSAJE — Bytes Creativos*\n\n` +
            `🟢 *WhatsApp Business*\n` +
            `👤 *De:* ${nombre}\n` +
            `💬 *Mensaje:* ${texto}\n` +
            `🕐 *Hora:* ${hora}\n\n` +
            `🔗 https://business.facebook.com/latest/inbox/all`
        );
        return;
    }
}

// ─── Frases motivacionales ────────────────────────────────────────────────────
const FRASES = [
    { texto: "El secreto del éxito es aprender a usar el dolor y el placer en lugar de que el dolor y el placer te usen a ti.", autor: "Tony Robbins" },
    { texto: "No es lo que nos pasa lo que determina nuestra vida, sino las decisiones que tomamos.", autor: "Tony Robbins" },
    { texto: "Si haces lo que siempre has hecho, obtendrás lo que siempre has obtenido.", autor: "Tony Robbins" },
    { texto: "El éxito es hacer lo que quieres, cuando quieres, donde quieres, con quien quieres, tanto como quieras.", autor: "Tony Robbins" },
    { texto: "La calidad de tu vida es la calidad de tus relaciones.", autor: "Tony Robbins" },
    { texto: "Los cambios ocurren cuando el dolor de quedarse igual supera al dolor de cambiar.", autor: "Tony Robbins" },
    { texto: "No hay fracasos en la vida, solo resultados.", autor: "Tony Robbins" },
    { texto: "Establece un objetivo tan grande que no puedas lograrlo hasta que te conviertas en alguien capaz de lograrlo.", autor: "Tony Robbins" },
    { texto: "La energía fluye hacia donde va la atención.", autor: "Tony Robbins" },
    { texto: "El único límite a tus logros de mañana son las dudas de hoy.", autor: "Tony Robbins" },
    { texto: "La gente de éxito hace preguntas. La gente mediocre tiene respuestas.", autor: "Tony Robbins" },
    { texto: "La forma en que te comunicás con vos mismo determina cómo te sentís respecto a tu vida.", autor: "Tony Robbins" },
    { texto: "Si no podés, debés. Si debés, podés.", autor: "Tony Robbins" },
    { texto: "El poder real no es poder sobre los demás, es el poder sobre uno mismo.", autor: "Tony Robbins" },
    { texto: "Una decisión tomada hoy puede cambiar el curso de tu vida para siempre.", autor: "Tony Robbins" },
    { texto: "El progreso es la fuente de la felicidad, no el logro final.", autor: "Tony Robbins" },
    { texto: "Vivir es dar. Dar es vivir.", autor: "Tony Robbins" },
    { texto: "Las personas exitosas hacen preguntas y buscan nuevos maestros constantemente.", autor: "Tony Robbins" },
    { texto: "Actúa como si lo que hacés marcara la diferencia. Lo hace.", autor: "Tony Robbins" },
    { texto: "Los ganadores toman decisiones de inmediato y las cambian lentamente. Los perdedores toman decisiones lentamente y las cambian de inmediato.", autor: "Tony Robbins" },
    { texto: "Dejá de vender. Empezá a ayudar.", autor: "Alex Hormozi" },
    { texto: "No tenés un problema de negocio, tenés un problema de habilidades.", autor: "Alex Hormozi" },
    { texto: "El dinero es solo la consecuencia de resolver los problemas de otras personas a escala.", autor: "Alex Hormozi" },
    { texto: "Tu oferta debe ser tan buena que la gente se sienta tonta al rechazarla.", autor: "Alex Hormozi" },
    { texto: "El volumen de trabajo que nadie más quiere hacer es exactamente donde vive tu ventaja competitiva.", autor: "Alex Hormozi" },
    { texto: "No compitas en precio, competí en valor.", autor: "Alex Hormozi" },
    { texto: "Las personas no compran productos, compran mejores versiones de sí mismas.", autor: "Alex Hormozi" },
    { texto: "Cuanto más específico sea tu nicho, más dinero vas a ganar.", autor: "Alex Hormozi" },
    { texto: "Hacé más de lo que funciona. Pará de hacer lo que no funciona. Simple.", autor: "Alex Hormozi" },
    { texto: "La riqueza se construye resolviendo el mismo problema una y otra vez, mejor cada vez.", autor: "Alex Hormozi" },
    { texto: "La diferencia entre donde estás y donde querés estar es el trabajo que no querés hacer.", autor: "Alex Hormozi" },
    { texto: "No construyas un negocio que te necesite. Construí un negocio que funcione sin vos.", autor: "Alex Hormozi" },
    { texto: "El cliente que más se queja es tu mejor consultor gratuito.", autor: "Alex Hormozi" },
    { texto: "Las habilidades de ventas son el multiplicador de todas tus otras habilidades.", autor: "Alex Hormozi" },
    { texto: "Dejá de intentar ser interesante. Sé útil.", autor: "Alex Hormozi" },
    { texto: "Si querés ser rico, trabajá en tu empresa. Si querés ser extraordinariamente rico, trabajá en vos mismo.", autor: "Alex Hormozi" },
    { texto: "La persona que está dispuesta a trabajar más duro que nadie siempre va a encontrar la manera.", autor: "Alex Hormozi" },
    { texto: "Si no estás avergonzado de la primera versión de tu producto, lo lanzaste demasiado tarde.", autor: "Alex Hormozi" },
    { texto: "La razón por la que no tenés lo que querés es que la versión de vos que sos ahora no puede sostenerlo.", autor: "Alex Hormozi" },
    { texto: "El emprendimiento es el arte de convertir el miedo en momentum.", autor: "Alex Hormozi" },
];

function getFraseDelDia() {
    const idx = new Date().getDate() % FRASES.length;
    return FRASES[idx];
}

// ─── Clima de José C. Paz ─────────────────────────────────────────────────────
async function getClima() {
    try {
        const r = await axios.get("https://wttr.in/Jose+C+Paz,Buenos+Aires?format=j1", {
            timeout: 8000,
            headers: { "User-Agent": "BytesCreativosBot/1.0" },
        });
        const cc   = r.data.current_condition[0];
        const desc = cc.lang_es?.[0]?.value || cc.weatherDesc[0].value;
        const temp = cc.temp_C;
        const sens = cc.FeelsLikeC;
        const hum  = cc.humidity;

        // Pronóstico de hoy
        const pronostico = r.data.weather[0];
        const maxTemp    = pronostico.maxtempC;
        const minTemp    = pronostico.mintempC;

        const emoji = parseInt(temp) >= 25 ? "☀️" :
                      parseInt(temp) >= 15 ? "⛅" :
                      parseInt(temp) >= 8  ? "🌥️" : "🥶";

        return `${emoji} *Clima — José C. Paz*\n` +
               `🌡️ Ahora: ${temp}°C (sensación ${sens}°C)\n` +
               `📊 Min/Max: ${minTemp}°C / ${maxTemp}°C\n` +
               `💧 Humedad: ${hum}%\n` +
               `☁️ ${desc}`;
    } catch (e) {
        console.error("❌ Error obteniendo clima:", e.message);
        return "🌤️ *Clima:* no disponible ahora";
    }
}

// ─── Reporte diario 9am ───────────────────────────────────────────────────────
async function sendDailyReport() {
    const hoy = new Date().toLocaleDateString("es-AR", {
        timeZone: "America/Argentina/Buenos_Aires",
        weekday: "long", day: "numeric", month: "long",
    });
    const hoyStr = hoy.charAt(0).toUpperCase() + hoy.slice(1);

    const frase = getFraseDelDia();
    const clima = await getClima();

    let reporte  = `🌅 *¡Buenos días, equipo Bytes!*\n`;
    reporte     += `📅 ${hoyStr}\n`;
    reporte     += `${"─".repeat(28)}\n\n`;
    reporte     += `💬 *"${frase.texto}"*\n`;
    reporte     += `— _${frase.autor}_\n\n`;
    reporte     += `${"─".repeat(28)}\n\n`;
    reporte     += `${clima}\n\n`;
    reporte     += `${"─".repeat(28)}\n\n`;
    reporte     += `📬 *Bandeja de mensajes:*\n`;
    reporte     += `• Meta: https://business.facebook.com/latest/inbox/all\n`;
    reporte     += `• Instagram: https://www.instagram.com/direct/inbox/\n\n`;
    reporte     += `_¡A romperla hoy! 💪🚀_`;

    await sendGroupAlert(reporte);
    console.log("📊 Reporte diario enviado");
}

let reporteScheduled = false;

function scheduleDaily9am() {
    if (reporteScheduled) return;
    reporteScheduled = true;
    function loop() {
        const now  = new Date();
        const next = new Date();
        next.setHours(9, 0, 0, 0);
        if (next <= now) next.setDate(next.getDate() + 1);
        const ms = next - now;
        console.log(`⏰ Próximo reporte diario en ${Math.round(ms / 60000)} minutos`);
        setTimeout(async () => { await sendDailyReport(); loop(); }, ms);
    }
    loop();
}

// ─── Servidor HTTP ────────────────────────────────────────────────────────────
http.createServer(async (req, res) => {
    const urlBase = req.url.split("?")[0];
    const qs      = new URLSearchParams(req.url.includes("?") ? req.url.split("?")[1] : "");

    // ── Broadcast (existente) ──
    if (req.method === "POST" && urlBase === "/broadcast") {
        let body = "";
        req.on("data", chunk => body += chunk);
        req.on("end", async () => {
            try {
                const { mensaje } = JSON.parse(body);
                if (!mensaje) {
                    res.writeHead(400, { "Content-Type": "application/json" });
                    return res.end(JSON.stringify({ error: "Falta el campo 'mensaje'" }));
                }
                const resultado = await enviarBroadcast(mensaje);
                res.writeHead(200, { "Content-Type": "application/json" });
                res.end(JSON.stringify(resultado));
            } catch (e) {
                res.writeHead(500, { "Content-Type": "application/json" });
                res.end(JSON.stringify({ error: e.message }));
            }
        });
        return;
    }

    // ── QR (existente) ──
    if (req.method === "GET" && urlBase === "/qr") {
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
        return;
    }

    // ── Listar grupos (para obtener JID del grupo interno) ──
    if (req.method === "GET" && urlBase === "/grupos") {
        if (!sockGlobal) {
            res.writeHead(503, { "Content-Type": "application/json" });
            res.end(JSON.stringify({ error: "Bot no conectado aún, esperá unos segundos" }));
            return;
        }
        try {
            const grupos = await sockGlobal.groupFetchAllParticipating();
            const lista  = Object.values(grupos).map(g => ({
                jid:           g.id,
                nombre:        g.subject,
                participantes: g.participants?.length || 0,
            }));
            res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
            res.end(JSON.stringify({ grupos: lista }, null, 2));
        } catch (e) {
            res.writeHead(500, { "Content-Type": "application/json" });
            res.end(JSON.stringify({ error: e.message }));
        }
        return;
    }

    // ── Meta webhook — verificación (GET) ──
    if (req.method === "GET" && urlBase === "/webhook/meta") {
        const mode      = qs.get("hub.mode");
        const token     = qs.get("hub.verify_token");
        const challenge = qs.get("hub.challenge");
        if (mode === "subscribe" && token === META_VERIFY_TOKEN) {
            console.log("✅ Meta webhook verificado correctamente");
            res.writeHead(200);
            res.end(challenge);
        } else {
            console.warn("⚠️ Verificación Meta fallida — token incorrecto");
            res.writeHead(403);
            res.end("Forbidden");
        }
        return;
    }

    // ── Meta webhook — eventos (POST) ──
    if (req.method === "POST" && urlBase === "/webhook/meta") {
        let rawBody = "";
        req.on("data", chunk => { rawBody += chunk; });
        req.on("end", async () => {
            res.writeHead(200);
            res.end("EVENT_RECEIVED");
            try {
                const body = JSON.parse(rawBody);
                await procesarMetaWebhook(body);
            } catch (e) {
                console.error("❌ Error procesando webhook Meta:", e.message);
            }
        });
        return;
    }

    // ── Test reporte diario ──
    if (req.method === "GET" && urlBase === "/test-reporte") {
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ ok: true, mensaje: "Enviando reporte de prueba..." }));
        sendDailyReport();
        return;
    }

    // Default
    res.writeHead(200);
    res.end("OK");
}).listen(PORT, () =>
    console.log(`🌍 Servidor activo en puerto ${PORT} — QR en /qr`)
);

// ─── Broadcast ────────────────────────────────────────────────────────────────
async function enviarBroadcast(mensaje) {
    if (!fbDb) throw new Error("Firebase no disponible");
    if (!sockGlobal) throw new Error("WhatsApp no conectado");

    const snap = await fbDb.ref("wa_usuarios").once("value");
    if (!snap.exists()) return { enviados: 0, errores: 0 };

    const usuarios = snap.val();
    let enviados = 0, errores = 0;

    for (const [uidEsc, datos] of Object.entries(usuarios)) {
        const nombre = datos?.nombre || "estudiante";
        const jid    = uidEsc
            .replace(/___DOT___/g, ".")
            .replace(/___AT___/g, "@")
            .replace(/___PLUS___/g, "+");

        const texto = mensaje.replace("{nombre}", nombre);

        try {
            await sockGlobal.sendMessage(jid, { text: texto });
            console.log(`📤 Broadcast → ${jid}`);
            enviados++;
        } catch (e) {
            console.error(`❌ Error enviando a ${jid}:`, e.message);
            errores++;
        }

        // Pausa entre mensajes para no activar anti-spam de WhatsApp
        await new Promise(r => setTimeout(r, 4000 + Math.random() * 2000));
    }

    return { enviados, errores };
}

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
            qrDataUrl  = null;
            sockGlobal = sock;
            console.log("✅ WhatsApp conectado — Bot TUCE + Alertas Bytes activos");
            await uploadSession();
            scheduleDaily9am(); // reporte diario a las 9am (se programa una sola vez)
        }
        if (connection === "close") {
            sockGlobal = null;
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
