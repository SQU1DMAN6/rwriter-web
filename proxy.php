<?php
session_start();

$backend = "http://152.53.36.187:8080"; // AI backend
$path = $_GET["path"] ?? "";
$url = $backend . "/" . ltrim($path, "/");

// Initialize cURL
$ch = curl_init($url);
curl_setopt($ch, CURLOPT_CUSTOMREQUEST, $_SERVER["REQUEST_METHOD"]);
curl_setopt($ch, CURLOPT_HTTPHEADER, ["Content-Type: application/json"]);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, false); // streaming

if ($_SERVER["REQUEST_METHOD"] === "POST") {
    $input = file_get_contents("php://input");
    curl_setopt($ch, CURLOPT_POSTFIELDS, $input);
}

// Stream the response directly
curl_setopt($ch, CURLOPT_WRITEFUNCTION, function ($curl, $data) {
    echo $data;
    ob_flush();
    flush();
    return strlen($data);
});

$httpcode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
curl_exec($ch);

curl_close($ch);
