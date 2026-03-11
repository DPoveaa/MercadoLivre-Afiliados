const wppconnect = require('@wppconnect-team/wppconnect');
const express = require('express');
const bodyParser = require('body-parser');
const fs = require('fs');
const path = require('path');
const axios = require('axios');
const FormData = require('form-data');
require('dotenv').config();

/**
 * WPPConnect Bridge Server - Versão Robusta v2.0
 * Gerencia a conexão com WhatsApp de forma autônoma e resiliente.
 */

const app = express();
app.use(bodyParser.json({ limit: '10mb' }));

// Configurações Globais
const PORT = process.env.PORT ? parseInt(process.env.PORT) : 21465;
const TELEGRAM_BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN;
const ADMIN_CHAT_IDS = process.env.ADMIN_CHAT_IDS ? process.env.ADMIN_CHAT_IDS.split(',').map(id => id.trim()) : [];
const SESSION_NAME = 'default';

// Caminhos de Persistência
const TOKENS_ROOT = path.join(__dirname, 'tokens');
const SESSION_PATH = path.join(TOKENS_ROOT, SESSION_NAME);
const USER_DATA_PATH = path.join(SESSION_PATH, 'userData');

// Estado Interno
let client = null;
let status = 'DISCONNECTED'; // DISCONNECTED, STARTING, QRCODE, CONNECTED, ERROR
let currentQr = null;
let lastQrSent = null;
let starting = false;
let sessionStartTime = 0;

// Garantir diretórios iniciais
if (!fs.existsSync(TOKENS_ROOT)) fs.mkdirSync(TOKENS_ROOT, { recursive: true });

// --- Utilitários ---

function log(level, message, data = '') {
    const ts = new Date().toISOString();
    const dataStr = data ? ` | ${JSON.stringify(data)}` : '';
    console.log(`[${ts}] [${level}] ${message}${dataStr}`);
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Envia notificações e fotos (QR Code) para o Telegram dos administradores
 */
async function notifyAdmins(message, base64Qr = null) {
    if (!TELEGRAM_BOT_TOKEN || ADMIN_CHAT_IDS.length === 0) return;

    for (const chatId of ADMIN_CHAT_IDS) {
        try {
            if (base64Qr) {
                const form = new FormData();
                const base64Image = base64Qr.split(';base64,').pop();
                const buffer = Buffer.from(base64Image, 'base64');
                
                form.append('chat_id', chatId);
                form.append('photo', buffer, { filename: 'qrcode.png' });
                form.append('caption', message);
                form.append('parse_mode', 'Markdown');

                await axios.post(`https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendPhoto`, form, {
                    headers: form.getHeaders(),
                    timeout: 30000
                });
            } else {
                await axios.post(`https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage`, {
                    chat_id: chatId,
                    text: message,
                    parse_mode: 'Markdown'
                }, { timeout: 10000 });
            }
        } catch (e) {
            log('ERROR', `[Telegram] Falha ao notificar ${chatId}`, e.response?.data || e.message);
        }
    }
}

// --- Núcleo WPPConnect ---

async function initializeClient() {
    if (client || starting) return;
    
    starting = true;
    status = 'STARTING';
    currentQr = null;
    log('INFO', `Iniciando sessão '${SESSION_NAME}'...`);

    try {
        const isLinux = process.platform === 'linux';
        let executablePath = undefined;
        
        if (isLinux) {
            const candidates = [
                '/usr/bin/google-chrome', 
                '/usr/bin/chromium-browser', 
                '/snap/bin/chromium', 
                '/usr/bin/chromium'
            ];
            for (const p of candidates) {
                if (fs.existsSync(p)) {
                    executablePath = p;
                    log('INFO', `Chrome detectado em: ${p}`);
                    break;
                }
            }
        }

        client = await wppconnect.create({
            session: SESSION_NAME,
            folderNameToken: TOKENS_ROOT,
            mkdirFolderToken: true,
            tokenStore: 'file',
            catchQR: (base64Qr) => {
                currentQr = base64Qr.startsWith('data:') ? base64Qr : `data:image/png;base64,${base64Qr}`;
                status = 'QRCODE';
                
                if (currentQr !== lastQrSent) {
                    log('INFO', 'Novo QR Code gerado');
                    notifyAdmins("📲 *WhatsApp Desconectado*\nEscaneie o QR Code abaixo para conectar o servidor de promoções.", currentQr);
                    lastQrSent = currentQr;
                }
            },
            statusFind: (statusSession) => {
                log('INFO', `Evento de status: ${statusSession}`);
                
                switch(statusSession) {
                    case 'inChat':
                    case 'isLogged':
                    case 'qrReadSuccess':
                        status = 'CONNECTED';
                        currentQr = null;
                        lastQrSent = null;
                        if (statusSession === 'qrReadSuccess') {
                            notifyAdmins("✅ *Conexão estabelecida!*\nO QR Code foi lido com sucesso.");
                        }
                        break;
                    case 'notLogged':
                    case 'desconnectedMobile':
                    case 'deviceNotConnected':
                        status = 'DISCONNECTED';
                        break;
                    case 'browserClose':
                    case 'autocloseCalled':
                        status = 'DISCONNECTED';
                        client = null;
                        starting = false;
                        break;
                    default:
                        status = statusSession.toUpperCase();
                }
            },
            headless: true,
            useChrome: !!executablePath,
            autoClose: false,
            waitForLogin: true,
            disableWelcome: true,
            updatesLog: false,
            debug: false,
            puppeteerOptions: {
                userDataDir: USER_DATA_PATH,
                executablePath: executablePath,
                args: [
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--no-first-run',
                    '--no-zygote',
                    '--window-size=1280,720',
                    '--disable-blink-features=AutomationControlled',
                    `--user-data-dir=${USER_DATA_PATH}`
                ]
            }
        });

        // Garantia de desativação de autoClose
        if (client && typeof client.disableAutoClose === 'function') {
            await client.disableAutoClose();
        }

        sessionStartTime = Date.now();
        starting = false;
        log('INFO', 'Sessão inicializada com sucesso');

    } catch (error) {
        log('ERROR', 'Erro fatal ao iniciar WPPConnect', error.message);
        status = 'ERROR';
        client = null;
        starting = false;
        await notifyAdmins(`❌ *Erro Crítico no Servidor WPP*\n${error.message}`);
    }
}

// Função para garantir que o cliente esteja pronto antes de qualquer operação
async function ensureClientReady() {
    if (status === 'CONNECTED' && client) return true;
    
    if (starting) {
        log('INFO', 'Servidor já está inicializando, aguardando...');
        // Aguarda até 60s pela inicialização em curso
        for (let i = 0; i < 30; i++) {
            await sleep(2000);
            if (status === 'CONNECTED') return true;
        }
        return false;
    }

    log('INFO', 'Inicialização sob demanda solicitada...');
    await initializeClient();
    
    // Aguarda o status mudar para CONNECTED ou QRCODE
    for (let i = 0; i < 30; i++) {
        await sleep(2000);
        if (status === 'CONNECTED') return true;
        if (status === 'QRCODE') return false; // Se caiu no QR, não está "ready" para enviar
    }
    
    return status === 'CONNECTED';
}

// Endpoints API REST

// Status Completo
app.get('/api/status', async (req, res) => {
    let extra = {};
    if (client && status === 'CONNECTED') {
        try {
            extra = {
                isLoggedIn: await client.isLoggedIn(),
                connectionState: await client.getConnectionState(),
                battery: await client.getBatteryLevel().catch(() => 'N/A'),
                isReady: true
            };
        } catch (e) {}
    }
    
    res.json({
        status: 'success',
        session: SESSION_NAME,
        internalStatus: status,
        starting: starting,
        hasQr: !!currentQr,
        ...extra
    });
});

// Enviar Mensagem de Texto
app.post('/api/send-message', async (req, res) => {
    const isReady = await ensureClientReady();
    if (!isReady || !client) {
        return res.status(400).json({ 
            status: 'error', 
            message: status === 'QRCODE' ? 'Necessário ler QR Code' : 'WhatsApp não está conectado',
            state: status 
        });
    }
    
    const { phone, message, groupId } = req.body;
    if (!message || (!phone && !groupId)) {
        return res.status(400).json({ status: 'error', message: 'Parâmetros insuficientes' });
    }

    try {
        const dest = groupId || (phone.includes('@') ? phone : `${phone}@c.us`);
        const result = await client.sendText(dest, message);
        res.json({ status: 'success', result });
    } catch (e) {
        log('ERROR', `Falha ao enviar mensagem para ${phone || groupId}`, e.message);
        res.status(500).json({ status: 'error', message: e.toString() });
    }
});

// Enviar Arquivo/Imagem
app.post('/api/send-file', async (req, res) => {
    const isReady = await ensureClientReady();
    if (!isReady || !client) {
        return res.status(400).json({ 
            status: 'error', 
            message: status === 'QRCODE' ? 'Necessário ler QR Code' : 'WhatsApp não está conectado',
            state: status 
        });
    }

    const { phone, groupId, url, caption, fileName } = req.body;
    if (!url || (!phone && !groupId)) {
        return res.status(400).json({ status: 'error', message: 'Parâmetros insuficientes' });
    }

    try {
        const dest = groupId || (phone.includes('@') ? phone : `${phone}@c.us`);
        const result = await client.sendFile(dest, url, fileName || 'arquivo', caption || '');
        res.json({ status: 'success', result });
    } catch (e) {
        log('ERROR', `Falha ao enviar arquivo para ${phone || groupId}`, e.message);
        res.status(500).json({ status: 'error', message: e.toString() });
    }
});

// Health Check Simples para os Scrapers
app.get('/api/:session/check-connection-state', (req, res) => {
    res.json({ status: 'success', state: status });
});

// Inicialização do Servidor Express
app.listen(PORT, '0.0.0.0', () => {
    log('INFO', `WPPConnect Bridge Server rodando na porta ${PORT} (Sem Watchdog)`);
});
