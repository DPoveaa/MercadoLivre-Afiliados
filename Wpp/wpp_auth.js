require('dotenv').config();
const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode');
const TelegramBot = require('node-telegram-bot-api');
const fs = require('fs');
const path = require('path');

const TELEGRAM_TOKEN = process.env.TELEGRAM_BOT_TOKEN;
const TELEGRAM_CHAT_ID = process.env.TELEGRAM_CHAT_ID;

const bot = new TelegramBot(TELEGRAM_TOKEN);

// Verifica se o diretório de autenticação existe e está corrompido
const authDir = path.join(process.cwd(), '.wwebjs_auth');
if (fs.existsSync(authDir)) {
    console.log('Diretório de autenticação encontrado:', authDir);
    try {
        const files = fs.readdirSync(authDir);
        console.log('Arquivos de autenticação:', files);
        
        // Verifica se os arquivos essenciais existem
        const essentialFiles = ['session.data', 'session.data.json'];
        const hasEssentialFiles = essentialFiles.some(file => files.includes(file));
        
        if (!hasEssentialFiles) {
            console.log('Arquivos essenciais de autenticação não encontrados. Removendo diretório...');
            fs.rmSync(authDir, { recursive: true, force: true });
            console.log('Diretório de autenticação removido.');
        } else {
            console.log('Arquivos de autenticação parecem válidos.');
        }
    } catch (error) {
        console.log('Erro ao ler diretório de autenticação:', error.message);
        console.log('Removendo diretório corrompido...');
        try {
            fs.rmSync(authDir, { recursive: true, force: true });
            console.log('Diretório de autenticação removido.');
        } catch (rmError) {
            console.log('Erro ao remover diretório:', rmError.message);
        }
    }
} else {
    console.log('Diretório de autenticação não encontrado. Será criado automaticamente.');
}

const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: { headless: true, args: ['--no-sandbox', '--disable-setuid-sandbox'] }
});

let lastTelegramQrMsgId = null;
let qrSent = false;
let authTimeout = null;

// Timeout para autenticação (2 minutos)
const AUTH_TIMEOUT = 120000; // 2 minutos

client.on('qr', async (qrCode) => {
    console.log('Enviando QR code para o Telegram...');
    qrSent = true;
    
    // Limpa timeout anterior se existir
    if (authTimeout) {
        clearTimeout(authTimeout);
    }
    
    // Define novo timeout
    authTimeout = setTimeout(() => {
        console.log('Timeout de autenticação atingido. Saindo com código 1.');
        process.exit(1);
    }, AUTH_TIMEOUT);
    
    const qrImageBuffer = await qrcode.toBuffer(qrCode);
    const sentMsg = await bot.sendPhoto(TELEGRAM_CHAT_ID, qrImageBuffer, { caption: 'Escaneie este QR code para autenticar o WhatsApp.' });
    lastTelegramQrMsgId = sentMsg.message_id;
});

client.on('ready', async () => {
    console.log('Cliente está pronto!');
    
    // Limpa timeout se autenticado
    if (authTimeout) {
        clearTimeout(authTimeout);
    }
    
    if (lastTelegramQrMsgId) {
        await bot.deleteMessage(TELEGRAM_CHAT_ID, lastTelegramQrMsgId).catch(() => {});
        lastTelegramQrMsgId = null;
        await bot.sendMessage(TELEGRAM_CHAT_ID, '✅ WhatsApp autenticado com sucesso!');
    }
    process.exit(0); // Encerra o processo com sucesso após autenticação
});

client.on('auth_failure', () => {
    console.error('Falha na autenticação. Será necessário escanear o QR novamente.');
    bot.sendMessage(TELEGRAM_CHAT_ID, '❌ Falha na autenticação do WhatsApp. Escaneie o QR code novamente.');
    
    // Remove o diretório de autenticação corrompido
    try {
        if (fs.existsSync(authDir)) {
            fs.rmSync(authDir, { recursive: true, force: true });
            console.log('Diretório de autenticação removido devido à falha.');
        }
    } catch (error) {
        console.log('Erro ao remover diretório após falha:', error.message);
    }
    
    process.exit(1); // Sai com código de erro
});

client.on('disconnected', (reason) => {
    console.log('Cliente desconectado:', reason);
    bot.sendMessage(TELEGRAM_CHAT_ID, `⚠️ WhatsApp desconectado: ${reason}`);
    process.exit(1); // Sai com código de erro
});

// Tratamento de erros não capturados
process.on('uncaughtException', (error) => {
    console.error('Erro não capturado:', error);
    process.exit(1);
});

process.on('unhandledRejection', (reason, promise) => {
    console.error('Promise rejeitada não tratada:', reason);
    process.exit(1);
});

// Verifica se já está autenticado após um tempo
setTimeout(() => {
    if (!qrSent) {
        console.log('Nenhum QR code foi enviado. Verificando se já está autenticado...');
        // Se não enviou QR code em 10 segundos, verifica se realmente está autenticado
        // Aguarda mais um pouco para ver se o cliente realmente conecta
        setTimeout(() => {
            if (!qrSent) {
                console.log('Cliente parece estar autenticado. Saindo com sucesso.');
                process.exit(0);
            }
        }, 5000); // Aguarda mais 5 segundos para confirmar
    }
}, 10000); // Aguarda 10 segundos

client.initialize(); 