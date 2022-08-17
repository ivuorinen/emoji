<?php

$output        = 'README.md';
$per_row       = 5;
$files         = glob( 'emoji/*.{png,gif,jpg,jpeg}', GLOB_BRACE );
$listing       = [];
$per_row_width = floor( 100 / $per_row ) . '%';

sort( $files );

if ( count( $files ) < 1 ) {
    die( 'No images to continue with.' );
}

function get_basename( string $file ) {
    $parts = explode( DIRECTORY_SEPARATOR, $file );
    return end( $parts );
}

foreach ( $files as $file ) {
    $first = get_basename( $file );
    $first = str_replace( 'emoji/', '', $first );
    $first = trim( $first[0] );

    if ( preg_match( '/([^a-zA-Z:])/', $first ) ) {
        $first = '\[^a-zA-Z:\]';
    }

    if ( ! array_key_exists( $first, $listing ) ) {
        $listing[ $first ] = [];
    }

    $listing[ $first ][] = $file;
}

$contents = "# Emotes\n\n";

$contents .= sprintf(
    "Listing of %d emojis last refreshed: %s",
    count($files),
    date('c')
) . "\n\n";

$contents .= "<!-- markdownlint-disable-file MD033 -->\n";

foreach ( $listing as $header => $icons ) {
    $contents .= sprintf( "\n## %s\n\n", $header );

    $chunks = array_chunk( $icons, $per_row );

    $contents .= '<div style="text-align: center;display:grid;grid-template-columns: repeat(5, 1fr);grid-template-rows: minmax(70px, auto);">' . "\n";

    foreach ( $chunks as $chunk_icons ) {
        foreach ( $chunk_icons as $icon ) {
            $file = $icon;
            [ $name, $ext ] = explode( '.', get_basename($icon), 2 );

            $format   = '<div style=\'border:1px solid #eee;padding:.5rem\'>'
                . '<img width=\'30\' src="%1$s" alt="%1$s"><br>'
                . '<kbd style=\'display:inline-block;max-width: 15vw;white-space: nowrap;overflow:auto\'>%2$s</kbd></div>';
            $contents .= sprintf( $format, $file, $name ) . "\n";
        }
    }

    $contents .= "</div>\n";
}

file_put_contents( $output, $contents );
