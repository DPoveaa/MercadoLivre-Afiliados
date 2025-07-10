require('dotenv').config();
const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode');
const TelegramBot = require('node-telegram-bot-api');
const fs = require('fs');
const path = require('path');

const TELEGRAM_TOKEN = process.env.TELEGRAM_BOT_TOKEN;
const TELEGRAM_CHAT_ID = process.env.TELEGRAM_CHAT_ID;

const bot = new TelegramBot(TELEGRAM_TOKEN);

// Verifica se o diretório de autenticação existe
const authDir = path.join(process.cwd(), '.wwebjs_auth');
if (fs.existsSync(authDir)) {
    const files = fs.readdirSync(authDir);
    const sessionFiles = ['session', 'session.data', 'session.data.json', 'session-whatsapp-client'];
    const hasAnySessionFile = sessionFiles.some(file => files.includes(file));
    
    if (!hasAnySessionFile) {
        fs.rmSync(authDir, { recursive: true, force: true });
    }
}

const client = new Client({
    authStrategy: new LocalAuth({
        clientId: 'whatsapp-client'
    }),
    puppeteer: { 
        headless: true, 
        args: [
            '--no-sandbox', 
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            '--disable-gpu',
            '--disable-web-security',
            '--disable-features=VizDisplayCompositor',
            '--disable-background-timer-throttling',
            '--disable-backgrounding-occluded-windows',
            '--disable-renderer-backgrounding'
        ] 
    }
});

let lastTelegramQrMsgId = null;
let qrSent = false;
let authTimeout = null;
let qrCount = 0;

// Timeout para autenticação (2 minutos)
const AUTH_TIMEOUT = 120000;

client.on('qr', async (qrCode) => {
    qrCount++;
    qrSent = true;
    
    if (authTimeout) {
        clearTimeout(authTimeout);
    }
    
    authTimeout = setTimeout(() => {
        console.log('Timeout de autenticação atingido.');
        process.exit(1);
    }, AUTH_TIMEOUT);
    
    const qrImageBuffer = await qrcode.toBuffer(qrCode);
    const caption = `🔐 QR Code #${qrCount} - Escaneie para autenticar o WhatsApp\n\n⚠️ Se não funcionar, aguarde o próximo QR code.`;
    
    // Deleta QR code anterior se existir
    if (lastTelegramQrMsgId) {
        await bot.deleteMessage(TELEGRAM_CHAT_ID, lastTelegramQrMsgId).catch(() => {});
    }
    
    const sentMsg = await bot.sendPhoto(TELEGRAM_CHAT_ID, qrImageBuffer, { caption });
    lastTelegramQrMsgId = sentMsg.message_id;
});

client.on('loading_screen', (percent, message) => {
    if (percent === 100) {
        console.log('WhatsApp carregado completamente.');
    }
});

client.on('authenticated', () => {
    console.log('Cliente autenticado com sucesso!');
});

client.on('auth_failure', (msg) => {
    console.error('Falha na autenticação:', msg);
    bot.sendMessage(TELEGRAM_CHAT_ID, '❌ Falha na autenticação do WhatsApp. Escaneie o QR code novamente.');
    
    try {
        if (fs.existsSync(authDir)) {
            fs.rmSync(authDir, { recursive: true, force: true });
        }
    } catch (error) {
        console.log('Erro ao remover diretório:', error.message);
    }
    
    process.exit(1);
});

client.on('ready', async () => {
    console.log('Cliente está pronto!');
    
    if (authTimeout) {
        clearTimeout(authTimeout);
    }
    
    if (lastTelegramQrMsgId) {
        await bot.deleteMessage(TELEGRAM_CHAT_ID, lastTelegramQrMsgId).catch(() => {});
        await bot.sendMessage(TELEGRAM_CHAT_ID, '✅ WhatsApp autenticado com sucesso!');
    }
    
    setTimeout(() => {
        process.exit(0);
    }, 2000);
});

client.on('disconnected', (reason) => {
    console.log('Cliente desconectado:', reason);
    bot.sendMessage(TELEGRAM_CHAT_ID, `⚠️ WhatsApp desconectado: ${reason}`);
    process.exit(1);
});

// Tratamento de erros
process.on('uncaughtException', (error) => {
    console.error('Erro não capturado:', error);
    process.exit(1);
});

process.on('unhandledRejection', (reason, promise) => {
    console.error('Promise rejeitada:', reason);
    process.exit(1);
});

// Verifica se já está autenticado
setTimeout(() => {
    if (!qrSent) {
        setTimeout(() => {
            if (!qrSent) {
                console.log('Cliente autenticado. Saindo com sucesso.');
                process.exit(0);
            }
        }, 8000);
    }
}, 15000);

client.initialize(); 