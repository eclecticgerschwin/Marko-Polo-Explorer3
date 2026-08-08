<?php
/*
 * Marko Polo Explorer - server-side part joiner
 * Upload this file together with the .part01, .part02 ... files
 * into the markopolo/ folder, then open it once in your browser:
 *   http://marko.com.hr/markopolo/join.php
 * It reassembles the original files and deletes the parts.
 */
header('Content-Type: text/plain; charset=utf-8');
set_time_limit(600);

$dir = __DIR__;
$groups = [];

/* find all files named like  NAME.partNN  */
foreach (scandir($dir) as $f) {
    if (preg_match('/^(.+)\.part(\d+)$/', $f, $m)) {
        $groups[$m[1]][(int)$m[2]] = $f;
    }
}

if (!$groups) {
    echo "No .partNN files found in " . basename($dir) . " - nothing to do.\n";
    exit;
}

foreach ($groups as $target => $parts) {
    ksort($parts);
    $n = count($parts);
    $expected = max(array_keys($parts));
    if ($n != $expected) {
        echo "SKIP $target: found $n parts but highest is part$expected - upload the missing parts first.\n";
        continue;
    }
    $out = fopen("$dir/$target", 'wb');
    if (!$out) { echo "ERROR: cannot create $target (check folder permissions)\n"; continue; }
    $total = 0;
    foreach ($parts as $i => $pf) {
        $in = fopen("$dir/$pf", 'rb');
        while (!feof($in)) {
            $chunk = fread($in, 1048576);
            fwrite($out, $chunk);
            $total += strlen($chunk);
        }
        fclose($in);
    }
    fclose($out);
    echo "OK: built $target (" . round($total / 1048576, 1) . " MB) from $n parts\n";
    foreach ($parts as $pf) { unlink("$dir/$pf"); }
    echo "    parts deleted.\n";
}
echo "\nDone. Verify the downloads work, then you can delete join.php.\n";
