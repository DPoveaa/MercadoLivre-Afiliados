require('dotenv').config();
const { Client, LocalAuth } = require('whatsapp-web.js');
const fs = require('fs');
const path = require('path');

console.log('=== Verificação de Status da Autenticação WhatsApp ===');

const authDir = path.join(process.cwd(), '.wwebjs_auth');

// Verifica se o diretório existe
if (fs.existsSync(authDir)) {
    console.log('✅ Diretório de autenticação encontrado:', authDir);
    
    try {
        const files = fs.readdirSync(authDir);
        console.log('📁 Arquivos de autenticação:', files);
        
        if (files.length > 0) {
            console.log('📋 Conteúdo dos arquivos:');
            files.forEach(file => {
                const filePath = path.join(authDir, file);
                try {
                    const stats = fs.statSync(filePath);
                    console.log(`  - ${file}: ${stats.size} bytes, modificado em ${stats.mtime}`);
                } catch (error) {
                    console.log(`  - ${file}: Erro ao ler arquivo`);
                }
            });
        }
    } catch (error) {
        console.log('❌ Erro ao ler diretório:', error.message);
    }
} else {
    console.log('❌ Diretório de autenticação não encontrado');
}

// Tenta inicializar o cliente para verificar se está autenticado
console.log('\n🔍 Testando autenticação...');

const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: { headless: true, args: ['--no-sandbox', '--disable-setuid-sandbox'] }
});

let authTimeout = setTimeout(() => {
    console.log('⏰ Timeout: Cliente não respondeu em 30 segundos');
    process.exit(1);
}, 30000);

client.on('qr', (qrCode) => {
    console.log('❌ QR Code gerado - WhatsApp NÃO está autenticado');
    clearTimeout(authTimeout);
    process.exit(1);
});

client.on('ready', () => {
    console.log('✅ WhatsApp está autenticado e pronto!');
    clearTimeout(authTimeout);
    process.exit(0);
});

client.on('auth_failure', () => {
    console.log('❌ Falha na autenticação');
    clearTimeout(authTimeout);
    process.exit(1);
});

client.on('disconnected', (reason) => {
    console.log('❌ Cliente desconectado:', reason);
    clearTimeout(authTimeout);
    process.exit(1);
});

client.initialize(); 