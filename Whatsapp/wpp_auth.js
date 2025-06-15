const { Client, LocalAuth } = require('whatsapp-web.js');
const { sendQRToTelegram } = require('../Telegram/tl_auth');
const path = require('path');
const fs = require('fs');
require('dotenv').config({ path: path.resolve(__dirname, '..', '.env') });
const { sendTelegramMessage } = require('../Telegram/tl_enviar');

const TELEGRAM_BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN;
const TELEGRAM_CHAT_ID = process.env.TELEGRAM_CHAT_ID;

let qrFoiEscaneadoRecentemente = false;
let authTimeout = null;

console.log('Iniciando wpp_auth.js');

// Função para limpar os dados de autenticação
async function limparDadosAuth() {
    const authPath = path.resolve('./auth_data');
    if (fs.existsSync(authPath)) {
        try {
            fs.rmSync(authPath, { recursive: true, force: true });
            console.log('[CLEANUP] Dados de autenticação antigos removidos com sucesso');
            await sendTelegramMessage('🧹 Dados de autenticação antigos foram removidos.', null, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID);
        } catch (error) {
            console.error('[CLEANUP ERROR] Erro ao remover dados de autenticação:', error);
        }
    }
}

// Função para configurar timeout de autenticação
function setupAuthTimeout() {
    if (authTimeout) {
        clearTimeout(authTimeout);
    }
    
    authTimeout = setTimeout(async () => {
        console.error('[TIMEOUT] Tempo limite de autenticação excedido');
        await sendTelegramMessage('⏰ Tempo limite de autenticação excedido. Tentando novamente...', null, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID);
        process.exit(1);
    }, 300000); // 5 minutos
}

const client = new Client({
    authStrategy: new LocalAuth({ dataPath: './auth_data' }),
    puppeteer: {
        headless: true,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-blink-features=AutomationControlled',
            '--disable-gpu',
            '--disable-extensions',
            '--disable-software-rasterizer',
            '--disable-features=site-per-process',
            '--disable-web-security',
            '--disable-features=IsolateOrigins,site-per-process',
        ],
        executablePath: process.env.CHROME_PATH || undefined,
    }
});

client.on('ready', async () => {
    console.log('[READY] Cliente WhatsApp está pronto.');
    if (authTimeout) {
        clearTimeout(authTimeout);
    }

    // Se não teve QR recente, significa que já estava autenticado
    if (!qrFoiEscaneadoRecentemente) {
        await sendTelegramMessage('✅ WhatsApp já estava autenticado e está pronto.', null, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID);
    }

    process.exit(0);
});

client.on('qr', async (qr) => {
    console.log('[QR EVENT] Novo QR recebido');
    qrFoiEscaneadoRecentemente = true;
    
    // Limpa os dados de autenticação antigos quando receber um novo QR
    await limparDadosAuth();
    
    // Configura timeout para autenticação
    setupAuthTimeout();
    
    try {
        await sendQRToTelegram(qr, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID);
        console.log('[QR] QR Code enviado para o Telegram com sucesso');
    } catch (error) {
        console.error('[QR ERROR] Erro ao enviar QR para Telegram:', error);
    }

    // Lembrete se não escanear
    setTimeout(() => {
        if (qrFoiEscaneadoRecentemente) {
            sendTelegramMessage('⚠️ Lembrete: O QR Code ainda não foi escaneado.', null, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID);
        }
    }, 60000);
});

client.on('authenticated', async () => {
    console.log('[AUTHENTICATED] Autenticado com sucesso!');
    if (authTimeout) {
        clearTimeout(authTimeout);
    }
    
    if (qrFoiEscaneadoRecentemente) {
        await sendTelegramMessage('✅ WhatsApp autenticado com sucesso!', null, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID);
        qrFoiEscaneadoRecentemente = false; // reseta a flag
    }
    process.exit(0);
});

client.on('auth_failure', async (msg) => {
    console.error('[AUTH FAILURE]', msg);
    if (authTimeout) {
        clearTimeout(authTimeout);
    }
    
    await sendTelegramMessage(`❌ Falha na autenticação do WhatsApp:\n\n${msg}`, null, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID);
    process.exit(1);
});

async function reinicializarCliente() {
    console.log('[REINIT] Tentando reinicializar o cliente WhatsApp...');
    try {
        await client.destroy();
        // Aguarda um momento antes de reinicializar
        await new Promise(resolve => setTimeout(resolve, 5000));
        await client.initialize();
        console.log('[REINIT] Cliente reinicializado com sucesso');
    } catch (error) {
        console.error('[REINIT ERROR] Erro ao reinicializar cliente:', error);
        await sendTelegramMessage(`❌ Erro ao reinicializar o cliente WhatsApp:\n\n${error.message}`, null, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID);
        process.exit(1);
    }
}

client.on('disconnected', async (reason) => {
    console.log('[DISCONNECTED]', reason);
    if (authTimeout) {
        clearTimeout(authTimeout);
    }
    
    await sendTelegramMessage(`🔴 Bot do WhatsApp foi desconectado. Motivo: *${reason}*`, null, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID);
    await reinicializarCliente();
});

// Tratamento de erros não capturados
process.on('uncaughtException', async (error) => {
    console.error('[UNCAUGHT EXCEPTION]', error);
    if (authTimeout) {
        clearTimeout(authTimeout);
    }
    
    await sendTelegramMessage(`❌ Erro não tratado no processo de autenticação:\n\n${error.message}`, null, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID);
    process.exit(1);
});

process.on('unhandledRejection', async (reason, promise) => {
    console.error('[UNHANDLED REJECTION]', reason);
    if (authTimeout) {
        clearTimeout(authTimeout);
    }
    
    // Verifica se é um erro de contexto destruído
    if (reason.message && reason.message.includes('Execution context was destroyed')) {
        console.log('[CONTEXT ERROR] Detectado erro de contexto destruído, tentando reinicializar...');
        await reinicializarCliente();
        return;
    }
    
    await sendTelegramMessage(`❌ Promessa rejeitada não tratada:\n\n${reason}`, null, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID);
    process.exit(1);
});

try {
    console.log('[INIT] Iniciando cliente WhatsApp...');
    client.initialize();
} catch (error) {
    console.error('[INIT ERROR] Erro ao inicializar cliente:', error);
    process.exit(1);
}
