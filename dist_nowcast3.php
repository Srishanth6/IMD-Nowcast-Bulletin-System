<?php
header("Cache-Control: max-age=0");

$candidates = array(
    __DIR__ . DIRECTORY_SEPARATOR . "IMD_Nowcast_Bulletin.docx",
    __DIR__ . DIRECTORY_SEPARATOR . "telangana_nowcast.docx",
);

$path = null;
foreach ($candidates as $candidate) {
    if (is_file($candidate)) {
        $path = $candidate;
        break;
    }
}

if ($path === null) {
    http_response_code(404);
    header("Content-Type: text/plain; charset=UTF-8");
    echo "Nowcast bulletin has not been generated yet.";
    exit;
}

header("Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document");
header("Content-Disposition: attachment; filename=telangana_nowcast.docx");
header("Content-Length: " . filesize($path));
readfile($path);
