<?php
if (PHP_SAPI !== 'cli') { http_response_code(403); exit; }
$sites=['prolitech'=>'/home/rvbkkxiv/public_html','prolimax'=>'/home/rvbkkxiv/prolimax.com.ua'];
$site=$argv[1]??'';
if(!isset($sites[$site]))exit(1);
require $sites[$site].'/config.php';
mysqli_report(MYSQLI_REPORT_ERROR|MYSQLI_REPORT_STRICT);
try {
 $db=new mysqli(DB_HOSTNAME,DB_USERNAME,DB_PASSWORD,DB_DATABASE,defined('DB_PORT')?(int)DB_PORT:3306);
 $db->set_charset('utf8mb4');
 $p=DB_PREFIX;
 if(!preg_match('/^[a-zA-Z0-9_]*$/',$p))throw new Exception();
 $sources=['blog'=>['oct_blogcomments','comment_id'],'article'=>['review_article','review_article_id'],'review'=>['review','review_id'],'question'=>['oct_faq','faq_id']];
 $rows=[];
 foreach($sources as $kind=>$spec) {
  $extra=$kind==='question'?", CASE WHEN TRIM(COALESCE(answer,''))='' THEN '' ELSE SHA2(answer,256) END AS answer_hash":", '' AS answer_hash";
  $q=$db->query("SELECT `{$spec[1]}` AS id,date_added,date_modified {$extra} FROM `{$p}{$spec[0]}`");
  while($row=$q->fetch_assoc()) {$row['kind']=$kind;$rows[]=$row;}
 }
 echo json_encode($rows,JSON_UNESCAPED_UNICODE|JSON_THROW_ON_ERROR);
} catch(Throwable $e) {fwrite(STDERR,'Feedback read failed: '.$site.' code='.$e->getCode()."\n");exit(1);}
