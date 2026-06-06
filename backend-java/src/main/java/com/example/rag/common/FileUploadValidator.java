package com.example.rag.common;

import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.io.InputStream;
import java.util.Arrays;
import java.util.HexFormat;
import java.util.Set;
import java.util.regex.Pattern;

/**
 * 文件上传安全校验器
 *
 * <p>三重校验：
 * <ol>
 *   <li>文件扩展名白名单</li>
 *   <li>Magic Number（文件头魔数）校验 —— 防止扩展名伪造</li>
 *   <li>文件大小限制（默认 50MB）</li>
 * </ol>
 *
 * <p>支持的文件类型：PDF、DOCX、XLSX、TXT、MD</p>
 *
 * @author knowledge-rag-team
 */
@Slf4j
@Component
public class FileUploadValidator {

    /** 最大文件大小：50MB */
    public static final long MAX_FILE_SIZE = 50L * 1024 * 1024;

    /** 允许的文件扩展名 */
    private static final Set<String> ALLOWED_EXTENSIONS = Set.of(
            "pdf", "docx", "xlsx", "txt", "md"
    );

    /** 非法字符正则（用于文件名安全处理） */
    private static final Pattern ILLEGAL_FILENAME_PATTERN =
            Pattern.compile("[\\\\/:*?\"<>|\\x00-\\x1f]");

    /** 文件名最大长度 */
    private static final int MAX_FILENAME_LENGTH = 255;

    // ==================== 对外方法 ====================

    /**
     * 完整校验：Magic Number + 扩展名 + 大小
     *
     * @param file 上传的文件
     * @return 校验后的文件类型（小写），如 pdf / docx / txt
     * @throws BusinessException 校验失败
     */
    public String validate(MultipartFile file) {
        // 1. 空文件检查
        if (file == null || file.isEmpty()) {
            throw new BusinessException(400, "上传文件不能为空");
        }

        // 2. 大小校验
        validateSize(file);

        // 3. 文件名安全校验
        String safeFilename = sanitizeFilename(file.getOriginalFilename());

        // 4. 扩展名校验
        String extension = getExtension(safeFilename);

        // 5. Magic Number 校验
        validateMagicNumber(file, extension);

        return extension;
    }

    /**
     * 校验文件大小（≤ 50MB）
     */
    public void validateSize(MultipartFile file) {
        if (file.getSize() > MAX_FILE_SIZE) {
            throw new BusinessException(400,
                    String.format("文件大小超出限制：%.1fMB > 50MB",
                            file.getSize() / (1024.0 * 1024.0)));
        }
        if (file.getSize() == 0) {
            throw new BusinessException(400, "文件内容为空");
        }
    }

    /**
     * 文件名安全处理
     * <ul>
     *   <li>移除路径分隔符 / 非法字符</li>
     *   <li>限制长度</li>
     *   <li>防止目录穿越攻击</li>
     * </ul>
     */
    public String sanitizeFilename(String originalFilename) {
        if (originalFilename == null || originalFilename.isBlank()) {
            throw new BusinessException(400, "文件名不能为空");
        }

        // 1. 剥离路径（防止目录穿越，如 ../../etc/passwd）
        String name = originalFilename;
        int lastBackslash = name.lastIndexOf('\\');
        int lastSlash = name.lastIndexOf('/');
        int lastSep = Math.max(lastBackslash, lastSlash);
        if (lastSep >= 0) {
            name = name.substring(lastSep + 1);
        }

        // 2. 替换非法字符为下划线
        name = ILLEGAL_FILENAME_PATTERN.matcher(name).replaceAll("_");

        // 3. 去除首尾空格和点（Windows 不允许文件名以点结尾）
        name = name.trim().replaceAll("^\\.+|\\.+$", "");

        // 4. 如果处理后为空，生成默认名称
        if (name.isBlank()) {
            name = "unnamed_file";
        }

        // 5. 截断过长文件名（保留扩展名）
        if (name.length() > MAX_FILENAME_LENGTH) {
            String ext = getExtension(name);
            String baseName = name.substring(0, name.length() - ext.length() - 1);
            int maxBaseLen = MAX_FILENAME_LENGTH - ext.length() - 1;
            if (maxBaseLen > 0) {
                name = baseName.substring(0, Math.min(baseName.length(), maxBaseLen)) + "." + ext;
            } else {
                name = name.substring(0, MAX_FILENAME_LENGTH);
            }
        }

        return name;
    }

    /**
     * 获取文件扩展名（小写）
     */
    public String getExtension(String filename) {
        if (filename == null || !filename.contains(".")) {
            throw new BusinessException(400, "文件缺少扩展名");
        }
        String ext = filename.substring(filename.lastIndexOf('.') + 1).toLowerCase();
        if (ext.isBlank()) {
            throw new BusinessException(400, "文件扩展名不能为空");
        }
        return ext;
    }

    // ==================== 私有方法 ====================

    /**
     * Magic Number（文件头魔数）校验
     *
     * <p>通过读取文件头 8 字节，对比已知文件类型的魔数，
     * 防止攻击者通过修改扩展名绕过白名单。</p>
     *
     * <table>
     *   <tr><th>类型</th><th>魔数（十六进制）</th><th>偏移</th></tr>
     *   <tr><td>PDF</td><td>25 50 44 46</td><td>0</td></tr>
     *   <tr><td>DOCX/XLSX</td><td>50 4B 03 04</td><td>0</td></tr>
     *   <tr><td>TXT/MD</td><td>无固定魔数（跳过）</td><td>-</td></tr>
     * </table>
     */
    private void validateMagicNumber(MultipartFile file, String extension) {
        // TXT / MD 无固定魔数，仅校验扩展名
        if ("txt".equals(extension) || "md".equals(extension)) {
            return;
        }

        byte[] header = readFileHeader(file, 8);
        if (header == null || header.length < 4) {
            throw new BusinessException(400, "无法读取文件头，文件可能已损坏");
        }

        String hex = HexFormat.of().withUpperCase().formatHex(
                Arrays.copyOf(header, Math.min(header.length, 4)));

        switch (extension) {
            case "pdf" -> {
                // PDF: %PDF (25 50 44 46)
                if (!hex.startsWith("25504446")) {
                    throw new BusinessException(400,
                            "文件扩展名与内容不匹配：期望 PDF，但文件头为 " + hex);
                }
            }
            case "docx" -> {
                // DOCX: ZIP 格式 PK.. (50 4B 03 04)
                if (!hex.startsWith("504B0304")) {
                    throw new BusinessException(400,
                            "文件扩展名与内容不匹配：期望 DOCX，但文件头为 " + hex);
                }
            }
            case "xlsx" -> {
                // XLSX: ZIP 格式 PK.. (50 4B 03 04)
                if (!hex.startsWith("504B0304")) {
                    throw new BusinessException(400,
                            "文件扩展名与内容不匹配：期望 XLSX，但文件头为 " + hex);
                }
            }
            default -> throw new BusinessException(400, "不支持的文件类型: " + extension);
        }
    }

    /**
     * 读取文件头部指定字节数
     */
    private byte[] readFileHeader(MultipartFile file, int byteCount) {
        try (InputStream is = file.getInputStream()) {
            byte[] header = new byte[byteCount];
            int bytesRead = is.read(header);
            if (bytesRead <= 0) {
                return null;
            }
            return Arrays.copyOf(header, bytesRead);
        } catch (IOException e) {
            log.error("读取文件头失败: {}", file.getOriginalFilename(), e);
            return null;
        }
    }
}
