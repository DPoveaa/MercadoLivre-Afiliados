const fs = require('fs');
const path = require('path');

console.log('=== Limpeza do Diretório de Autenticação WhatsApp ===');

const authDir = path.join(process.cwd(), '.wwebjs_auth');

if (fs.existsSync(authDir)) {
    console.log('Diretório de autenticação encontrado:', authDir);
    
    try {
        const files = fs.readdirSync(authDir);
        console.log('Arquivos encontrados:', files);
        
        // Remove todos os arquivos e subdiretórios
        fs.rmSync(authDir, { recursive: true, force: true });
        console.log('✅ Diretório de autenticação removido com sucesso!');
        console.log('Agora execute o wpp_auth.js para reautenticar o WhatsApp.');
        
    } catch (error) {
        console.error('❌ Erro ao remover diretório:', error.message);
        process.exit(1);
    }
} else {
    console.log('Diretório de autenticação não encontrado.');
    console.log('Não há nada para limpar.');
}

console.log('=== Limpeza concluída ==='); 