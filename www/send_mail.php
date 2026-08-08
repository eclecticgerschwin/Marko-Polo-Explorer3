<?php
// Marko Polo Explorer - PHPMailer SMTP & API Contact Handler
use PHPMailer\PHPMailer\PHPMailer;
use PHPMailer\PHPMailer\Exception;

require_once __DIR__ . '/phpmailer/Exception.php';
require_once __DIR__ . '/phpmailer/PHPMailer.php';
require_once __DIR__ . '/phpmailer/SMTP.php';

if ($_SERVER["REQUEST_METHOD"] === "POST") {
    // Sanitize input fields
    $name     = isset($_POST['name']) ? strip_tags(trim($_POST['name'])) : '';
    $email    = filter_var(trim($_POST['email'] ?? ''), FILTER_SANITIZE_EMAIL);
    $category = isset($_POST['category']) ? strip_tags(trim($_POST['category'])) : 'Bug / Issue Report';
    $os       = isset($_POST['os']) ? strip_tags(trim($_POST['os'])) : 'N/A';
    $message  = isset($_POST['message']) ? strip_tags(trim($_POST['message'])) : '';

    // Basic validation
    if (empty($name) || empty($email) || empty($message) || !filter_var($email, FILTER_VALIDATE_EMAIL)) {
        header("Location: index.html?status=error#contact");
        exit;
    }

    $sent = false;

    // --- Attempt 1: PHPMailer via Authenticated SMTP ---
    try {
        $mail = new PHPMailer(true);
        $mail->isSMTP();
        $mail->Host       = 'smtp.gmail.com';             // SMTP Host (e.g., smtp.gmail.com or mail.marko.com.hr)
        $mail->SMTPAuth   = true;
        $mail->Username   = 'mcpseidon@gmail.com';         // SMTP Username
        $mail->Password   = 'YOUR_SMTP_PASSWORD';         // SMTP Password / App Password
        $mail->SMTPSecure = PHPMailer::ENCRYPTION_STARTTLS;
        $mail->Port       = 587;
        $mail->CharSet    = 'UTF-8';
        $mail->Timeout    = 8;

        $mail->setFrom('mcpseidon@gmail.com', 'Marko Polo Website');
        $mail->addAddress('mcpseidon@gmail.com', 'Marko Polo Support');
        $mail->addReplyTo($email, $name);

        $mail->isHTML(false);
        $mail->Subject = 'Marko Polo contact form';
        $mail->Body    = "Marko Polo Explorer - Contact Form\n===================================\nName: $name\nEmail: $email\nCategory: $category\nOS: $os\n\nMessage / Bug Details:\n$message\n";

        $mail->send();
        $sent = true;
    } catch (\Throwable $e) {
        // --- Attempt 2: HTTPS API Fallback (Bypasses local PHP mail() / sendmail restrictions) ---
        $post_data = array(
            'name'     => $name,
            'email'    => $email,
            'category' => $category,
            'os'       => $os,
            'message'  => $message,
            '_subject' => 'Marko Polo contact form',
            '_captcha' => 'false'
        );

        if (function_exists('curl_init')) {
            $ch = curl_init('https://formsubmit.co/ajax/mcpseidon@gmail.com');
            curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
            curl_setopt($ch, CURLOPT_POST, true);
            curl_setopt($ch, CURLOPT_POSTFIELDS, http_build_query($post_data));
            curl_setopt($ch, CURLOPT_HTTPHEADER, array('Accept: application/json'));
            curl_setopt($ch, CURLOPT_TIMEOUT, 8);
            $response = curl_exec($ch);
            $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
            curl_close($ch);

            if ($http_code == 200 || $response !== false) {
                $sent = true;
            }
        }
    }

    if ($sent) {
        header("Location: index.html?status=success#contact");
    } else {
        header("Location: index.html?status=error#contact");
    }
    exit;
} else {
    header("Location: index.html");
    exit;
}
